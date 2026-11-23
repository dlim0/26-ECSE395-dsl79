#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstring>
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "driver/usb_serial_jtag.h"
#include "esp_camera.h"
#include "esp_heap_caps.h"
#include "esp_psram.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "dl_image_jpeg.hpp"
#include "mbedtls/base64.h"
#include "status_display.hpp"
#include "approach_gate.hpp"
#ifdef VIBRATION_WIFI
#include "vibration_receiver.hpp"
#endif

namespace {
constexpr int W=80, H=60, N=W*H;
constexpr int BASELINE_FRAMES=12;
constexpr int PIXEL_DELTA=25;
#ifdef VIBRATION_WIFI
constexpr int MIN_REGION_PIXELS=336; // 7% of the analysis grid.
#else
constexpr int MIN_REGION_PIXELS=approach::minimumArea;
#endif
uint16_t baseline[N] = {};
#ifdef VIBRATION_WIFI
// RGB block averages preserve color changes lost by luminance conversion.
uint16_t baselineRgb[N][3] = {};
uint8_t blockRgb[N][3];
bool colorAssist=false;
// Provisional darkness gate: at least 75% of blocks below 20/255 luminance.
constexpr int DARK_BLOCK_LEVEL=20, COLOR_REGION_PIXELS=480;
uint8_t grayscaleMask[N];
#endif
uint8_t gray[N], mask[N], cleanMask[N];
uint16_t queuePixels[N];
int samples=0;
std::atomic<bool> relearn{false};
std::atomic<bool> speakerTest{false};
std::atomic<bool> rearm{false}, buzzerEnded{false};
#ifdef PIR_CAMERA_BENCH
enum class BenchTone { none, high, low, cycle };
std::atomic<BenchTone> benchTone{BenchTone::none};
constexpr gpio_num_t benchPirPin = GPIO_NUM_5;
constexpr gpio_num_t benchSpeakerPin = GPIO_NUM_10;
#endif
esp_timer_handle_t buzzerTimer=nullptr;
SemaphoreHandle_t buzzerMutex=nullptr;
int buzzerTicks=-1; // 100 ms ticks; -1 means idle.
bool cameraOnline=false;
unsigned deterrentCount=0;
#ifdef VIBRATION_WIFI
constexpr unsigned deterrentFrequencyHz = 8000;
#else
constexpr unsigned deterrentFrequencyHz = 2000;
#endif
approach::Gate growth;

void setWhite(bool on) {
    // Common-ground SunFounder RGB module: all channels HIGH makes white.
    gpio_set_level(GPIO_NUM_13,on);
    gpio_set_level(GPIO_NUM_36,on);
    gpio_set_level(GPIO_NUM_35,on);
}

camera_fb_t* captureWithWhiteFlash() {
    setWhite(true);
    vTaskDelay(pdMS_TO_TICKS(120));
    // The driver can already have an ambient-light frame queued. Discard two
    // frames so the returned image is exposed while the white light is ON.
    for(int i=0;i<2;++i) {
        auto stale=esp_camera_fb_get();
        if(!stale) {setWhite(false);return nullptr;}
        esp_camera_fb_return(stale);
    }
    auto frame=esp_camera_fb_get();
    setWhite(false);
    return frame;
}

void silenceBuzzer(void*) {
    xSemaphoreTake(buzzerMutex,portMAX_DELAY);
    const bool wasActive=buzzerTicks>=0;
    buzzerTicks=-1;
    setWhite(false);
    ledc_set_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_2,0);
    ledc_update_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_2);
    if(wasActive) buzzerEnded=true;
    xSemaphoreGive(buzzerMutex);
}
void buzzerPatternStep(void*) {
    bool finished=false;
    xSemaphoreTake(buzzerMutex,portMAX_DELAY);
    if(buzzerTicks>=0) {
        ++buzzerTicks;
        // ON 0-1.5s, OFF .5s, ON 2-3.5s, OFF .5s, ON 4-5.5s.
        finished=buzzerTicks>=55;
        const bool on=!finished && buzzerTicks%20<15;
        ledc_set_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_2,on?512:0);
        ledc_update_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_2);
        // White flashes at 5 Hz throughout the 5.5-second alarm.
        setWhite(!finished && buzzerTicks%2==0);
        if(finished) {buzzerTicks=-1;buzzerEnded=true;}
    }
    xSemaphoreGive(buzzerMutex);
    if(finished) esp_timer_stop(buzzerTimer);
}
bool initializeBuzzer() {
    // Separate timer/channel from the camera's timer 0/channel 0 clock.
    ledc_timer_config_t timer={};
    timer.speed_mode=LEDC_LOW_SPEED_MODE;timer.duty_resolution=LEDC_TIMER_10_BIT;
    timer.timer_num=LEDC_TIMER_1;timer.freq_hz=deterrentFrequencyHz;timer.clk_cfg=LEDC_AUTO_CLK;
    if(ledc_timer_config(&timer)!=ESP_OK) return false;
    ledc_channel_config_t channel={};
    channel.gpio_num=10;channel.speed_mode=LEDC_LOW_SPEED_MODE;
    channel.channel=LEDC_CHANNEL_2;channel.timer_sel=LEDC_TIMER_1;channel.duty=0;
    if(ledc_channel_config(&channel)!=ESP_OK) return false;
    buzzerMutex=xSemaphoreCreateMutex();
    if(!buzzerMutex) return false;
    esp_timer_create_args_t args={};
    args.callback=buzzerPatternStep;args.name="buzzer_pattern";
    return esp_timer_create(&args,&buzzerTimer)==ESP_OK;
}
bool soundDeterrent(unsigned frame) {
    esp_timer_stop(buzzerTimer);
    xSemaphoreTake(buzzerMutex,portMAX_DELAY);
    // Timer task controls the pattern independently of USB/image transfers.
    buzzerTicks=0;
    if(esp_timer_start_periodic(buzzerTimer,100000)!=ESP_OK) {
        buzzerTicks=-1;
        setWhite(false);
        ledc_set_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_2,0);
        ledc_update_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_2);
        xSemaphoreGive(buzzerMutex);
        return false;
    }
    ledc_set_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_2,512);
    ledc_update_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_2);
    setWhite(true);
    xSemaphoreGive(buzzerMutex);
    ++deterrentCount;
    std::printf("DETERRENT_ON frame=%u count=%u pulses=3 on_ms=1500 gap_ms=500 duration_ms=5500 frequency_hz=%u white_flash_hz=5\n",frame,deterrentCount,deterrentFrequencyHz);
    return true;
}
void cameraStandby() {
    if(cameraOnline) esp_camera_deinit();
    cameraOnline=false;
    gpio_set_level(GPIO_NUM_37,1);
    gpio_set_direction(GPIO_NUM_37,GPIO_MODE_OUTPUT);
}

using Region=approach::Region;
Region largestRegion() {
    // Majority filter removes isolated changing pixels; then find connected components.
    std::memset(cleanMask,0,N);
    for(int y=1;y<H-1;++y) for(int x=1;x<W-1;++x) {
        int neighbors=0;
        for(int dy=-1;dy<=1;++dy) for(int dx=-1;dx<=1;++dx) neighbors+=mask[(y+dy)*W+x+dx];
        cleanMask[y*W+x]=neighbors>=5;
    }
    Region best;
    for(int i=0;i<N;++i) {
        if(!cleanMask[i]) continue;
        int head=0,tail=0,x0=W,y0=H,x1=0,y1=0,area=0;
        queuePixels[tail++]=i; cleanMask[i]=0;
        while(head<tail) {
            int p=queuePixels[head++],x=p%W,y=p/W;
            ++area; x0=std::min(x0,x);x1=std::max(x1,x);y0=std::min(y0,y);y1=std::max(y1,y);
            const int next[4]={x>0?p-1:-1,x<W-1?p+1:-1,y>0?p-W:-1,y<H-1?p+W:-1};
            for(int q:next) if(q>=0 && cleanMask[q]) {cleanMask[q]=0;queuePixels[tail++]=q;}
        }
        if(area>best.area) best={area,x0,y0,x1-x0+1,y1-y0+1};
    }
    return best;
}

bool algorithmSelftest() {
    std::memset(mask,0,N);
    if(largestRegion().area!=0) return false;
    for(int y=10;y<34;++y) for(int x=10;x<34;++x) mask[y*W+x]=1;
    Region large=largestRegion();
    if(large.area<MIN_REGION_PIXELS || large.x!=10 || large.y!=10) return false;
    std::memset(mask,0,N);
    for(int y=10;y<15;++y) for(int x=10;x<15;++x) mask[y*W+x]=1;
    if(largestRegion().area>=MIN_REGION_PIXELS) return false;
    std::memset(mask,0,N);
    for(int p=0;p<N;p+=101) mask[p]=1;
    return largestRegion().area==0;
}

void cameraPowerSetup(bool driveAudioPin = true) {
    for(auto pair : {std::pair<int,int>{7,1},{45,0},{21,1},{10,0},{37,0}}) {
        if (pair.first == 10 && !driveAudioPin) continue;
        gpio_set_level(static_cast<gpio_num_t>(pair.first),pair.second);
        gpio_set_direction(static_cast<gpio_num_t>(pair.first),GPIO_MODE_OUTPUT);
    }
    // TFT CS remains HIGH and backlight LOW while its SPI pins drive RGB.
    for(auto pin : {GPIO_NUM_13,GPIO_NUM_36,GPIO_NUM_35}) {
        gpio_set_level(pin,0);
        gpio_set_direction(pin,GPIO_MODE_OUTPUT);
    }
    gpio_set_direction(GPIO_NUM_5,GPIO_MODE_INPUT);
    gpio_set_pull_mode(GPIO_NUM_5,GPIO_PULLDOWN_ONLY);
    vTaskDelay(pdMS_TO_TICKS(20));
}

esp_err_t cameraInit() {
    camera_config_t c={};
    c.pin_pwdn=37;c.pin_reset=-1;c.pin_xclk=17;
    c.pin_sccb_sda=1;c.pin_sccb_scl=41;
    c.pin_d0=8;c.pin_d1=12;c.pin_d2=14;c.pin_d3=11;
    c.pin_d4=15;c.pin_d5=9;c.pin_d6=16;c.pin_d7=6;
    c.pin_vsync=2;c.pin_href=18;c.pin_pclk=42;
    c.xclk_freq_hz=20000000;c.ledc_timer=LEDC_TIMER_0;c.ledc_channel=LEDC_CHANNEL_0;
    c.pixel_format=PIXFORMAT_JPEG;c.frame_size=FRAMESIZE_QVGA;
    c.jpeg_quality=12;c.fb_count=1;c.fb_location=CAMERA_FB_IN_PSRAM;c.grab_mode=CAMERA_GRAB_WHEN_EMPTY;
    return esp_camera_init(&c);
}

void commandTask(void*) {
    char command[64];
    while(true) {
        if(std::fgets(command,sizeof(command),stdin)) {
            if(std::strncmp(command,"BASELINE",8)==0) relearn=true;
            if(std::strncmp(command,"ARM",3)==0) rearm=true;
            if(std::strcmp(command,"SOUND\n")==0 || std::strcmp(command,"SOUND\r\n")==0) speakerTest=true;
#ifdef PIR_CAMERA_BENCH
            if(std::strcmp(command,"TONE\n")==0 || std::strcmp(command,"TONE\r\n")==0)
                benchTone = BenchTone::high;
            if(std::strcmp(command,"TONE_LOW\n")==0 || std::strcmp(command,"TONE_LOW\r\n")==0)
                benchTone = BenchTone::low;
            if(std::strcmp(command,"TONE_CYCLE\n")==0 || std::strcmp(command,"TONE_CYCLE\r\n")==0)
                benchTone = BenchTone::cycle;
#endif
        } else std::clearerr(stdin);
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

uint32_t fnv1a(const uint8_t* p,size_t length) {
    uint32_t hash=2166136261u;
    for(size_t i=0;i<length;++i) hash=(hash^p[i])*16777619u;
    return hash;
}
void transmitPhoto(unsigned n,camera_fb_t* fb,const char* metadata) {
    // Battery-only operation must not spend time streaming photos to no host.
    if(!usb_serial_jtag_is_connected()) return;
    std::printf("PHOTO_BEGIN %s\n",metadata);
    char encoded[257];
    for(size_t offset=0;offset<fb->len;offset+=180) {
        if(!usb_serial_jtag_is_connected()) return;
        size_t written=0;
        size_t size=std::min(size_t(180),fb->len-offset);
        if(mbedtls_base64_encode(reinterpret_cast<unsigned char*>(encoded),sizeof(encoded),&written,fb->buf+offset,size)!=0) break;
        encoded[written]=0;
        std::printf("PHOTO_DATA %s\n",encoded);
    }
    std::printf("PHOTO_END %u\n",n);
}

#ifdef PIR_CAMERA_BENCH
void playBenchTone(BenchTone tone) {
    const unsigned frequencyHz = tone == BenchTone::low ? 2000 : 8000;
    const unsigned pulses = tone == BenchTone::cycle ? 3 : 1;
    const unsigned durationMs = tone == BenchTone::cycle ? 1500 :
                                tone == BenchTone::low ? 1000 : 300;
    ledc_timer_config_t timer{};
    timer.speed_mode = LEDC_LOW_SPEED_MODE;
    timer.timer_num = LEDC_TIMER_1;
    timer.duty_resolution = LEDC_TIMER_8_BIT;
    timer.freq_hz = frequencyHz;
    timer.clk_cfg = LEDC_AUTO_CLK;
    ledc_channel_config_t output{};
    output.gpio_num = benchSpeakerPin;
    output.speed_mode = LEDC_LOW_SPEED_MODE;
    output.channel = LEDC_CHANNEL_2;
    output.timer_sel = LEDC_TIMER_1;
    output.duty = 0;
    if (ledc_timer_config(&timer) != ESP_OK || ledc_channel_config(&output) != ESP_OK) {
        gpio_set_direction(benchSpeakerPin, GPIO_MODE_INPUT);
        std::printf("ERROR bench_tone_setup\n");
        return;
    }
    std::printf("SPEAKER_TEST_ON frequency_hz=%u pulse_ms=%u pulses=%u\n",
                frequencyHz, durationMs, pulses);
    for (unsigned pulse = 0; pulse < pulses; ++pulse) {
        ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_2, 128);
        ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_2);
        vTaskDelay(pdMS_TO_TICKS(durationMs));
        ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_2, 0);
        ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_2);
        if (pulse + 1 < pulses) vTaskDelay(pdMS_TO_TICKS(500));
    }
    ledc_stop(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_2, 0);
    gpio_set_direction(benchSpeakerPin, GPIO_MODE_INPUT);
    std::printf("SPEAKER_TEST_OFF\n");
}

void captureBenchPhoto(unsigned frame) {
    esp_err_t result = cameraInit();
    if (result != ESP_OK) {
        std::printf("ERROR bench_camera_init=%s\n", esp_err_to_name(result));
        cameraStandby();
        return;
    }
    cameraOnline = true;
    vTaskDelay(pdMS_TO_TICKS(1200));
    auto* photo = captureWithWhiteFlash();
    if (photo) {
        char metadata[384];
        std::snprintf(metadata, sizeof(metadata),
                      "{\"frame\":%u,\"state\":\"CAMERA_TEST\",\"area_percent\":0,\"bbox\":[0,0,0,0],\"grid\":[80,60],\"pir\":%d,\"jpeg_bytes\":%u,\"fnv1a\":\"%08lx\"}",
                      frame, gpio_get_level(benchPirPin), unsigned(photo->len),
                      static_cast<unsigned long>(fnv1a(photo->buf, photo->len)));
        transmitPhoto(frame, photo, metadata);
        esp_camera_fb_return(photo);
    } else {
        std::printf("ERROR bench_camera_capture\n");
    }
    cameraStandby();
}
#endif
}

extern "C" void app_main() {
    setvbuf(stdout,nullptr,_IONBF,0);
#ifdef VIBRATION_WIFI
    cameraPowerSetup();
    cameraStandby();
    const esp_err_t wifiResult = vibration::start();
    if (wifiResult != ESP_OK) {
        std::printf("ERROR vibration_wifi=%s\n", esp_err_to_name(wifiResult));
        return;
    }
#ifdef VIBRATION_VERIFY
    if (!initializeBuzzer()) {
        std::printf("ERROR vibration_alarm_setup\n");
        return;
    }
    std::printf("READY VIBRATION_VERIFY ssid=%s endpoint=POST_/vibration\n", vibration::ssid);
    int64_t nextStatus = 0;
    while (true) {
        if (buzzerEnded.exchange(false)) std::printf("DETERRENT_OFF count=%u\n", deterrentCount);
        xSemaphoreTake(buzzerMutex, portMAX_DELAY);
        const bool sounding = buzzerTicks >= 0;
        xSemaphoreGive(buzzerMutex);
        if (vibration::takeFreshEvent()) {
            std::printf("VIBRATION_RECEIVED alarm_busy=%d\n", int(sounding));
            if (!sounding && !soundDeterrent(0)) std::printf("ERROR deterrent_timer\n");
        }
        const int64_t now = esp_timer_get_time();
        if (now >= nextStatus) {
            std::printf("STATUS state=VIBRATION_VERIFY deterrents=%u\n", deterrentCount);
            nextStatus = now + 2000000;
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
#else
    std::printf("READY VIBRATION_FUSION ssid=%s endpoint=POST_/vibration pir_high_ms=100 pir_low_ms=500 post_alarm_cooldown_ms=4500\n", vibration::ssid);
#endif
#endif
#ifdef PIR_DIAGNOSTIC
#ifdef PIR_CAMERA_BENCH
    cameraPowerSetup(false);
    gpio_set_direction(benchSpeakerPin, GPIO_MODE_INPUT);
    gpio_set_direction(benchPirPin, GPIO_MODE_INPUT);
    gpio_set_pull_mode(benchPirPin, GPIO_PULLDOWN_ONLY);
    constexpr gpio_num_t testPirPin = benchPirPin;
    xTaskCreate(commandTask, "bench_commands", 3072, nullptr, 3, nullptr);
#else
    cameraPowerSetup();
    constexpr gpio_num_t testPirPin = GPIO_NUM_5;
#endif
    cameraStandby();
    const int64_t started = esp_timer_get_time();
    const int64_t warmupUs = 60000000;
    const int64_t flashDurationUs = 250000;
    int64_t nextStatus = 0;
    int64_t highSince = 0;
    int64_t flashUntil = 0;
    bool armed = false;
    unsigned triggers = 0;
    while (true) {
#ifdef PIR_CAMERA_BENCH
        const BenchTone tone = benchTone.exchange(BenchTone::none);
        if (tone != BenchTone::none) playBenchTone(tone);
#endif
        const int64_t elapsed = esp_timer_get_time() - started;
        if (flashUntil && elapsed >= flashUntil) {
            setWhite(false);
            flashUntil = 0;
        }
        const bool high = gpio_get_level(testPirPin);
        if (elapsed >= warmupUs) {
            if (!high) {
                if (highSince) {
                    std::printf("PIR_LOW elapsed_ms=%lld high_ms=%lld\n",
                                elapsed / 1000, (elapsed - highSince) / 1000);
                    highSince = 0;
                }
                armed = true;
            } else if (armed) {
                armed = false;
                highSince = elapsed;
                setWhite(true);
                flashUntil = elapsed + flashDurationUs;
                std::printf("PIR_TRIGGER count=%u elapsed_ms=%lld\n", ++triggers, elapsed / 1000);
#ifdef PIR_CAMERA_BENCH
                vTaskDelay(pdMS_TO_TICKS(250));
                setWhite(false);
                flashUntil = 0;
                captureBenchPhoto(triggers);
#endif
            }
        }
        if (elapsed >= nextStatus) {
            const char* state = elapsed < warmupUs ? "WARMUP" :
                                armed ? "ARMED" : "WAIT_FOR_LOW";
            std::printf("PIR_TEST state=%s gpio=%d pir=%d elapsed_s=%lld triggers=%u\n",
                        state, int(testPirPin), int(high), elapsed / 1000000, triggers);
            nextStatus = elapsed + 1000000;
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
#endif
    vTaskDelay(pdMS_TO_TICKS(1500));
    std::printf("BOOT pir_size_deterrent buzzer=3_pulses_1500ms_on_500ms_gap rgb=WHITE photo_flash=ON alarm_flash_hz=5 tft=OFF\n");
    bool pass=algorithmSelftest();
    std::printf("MOTION_SELFTEST %s\n",pass?"PASS":"FAIL");
    if(!pass) return;
    bool growthPass=approach::selftest();
    std::printf("APPROACH_SELFTEST %s minimum_area_percent=10 window_frames=5 net_growth_percent=25 minimum_gain_pixels=96\n",growthPass?"PASS":"FAIL");
    if(!growthPass) return;
    cameraPowerSetup();
    std::printf("DISPLAY DISABLED rgb_R=13 rgb_G=36 rgb_B=35\n");
    status_display::show("STARTING","KEEP THE VIEW EMPTY",0xffe0);
    if(!initializeBuzzer()) {std::printf("ERROR buzzer_setup\n");status_display::show("BUZZER ERROR","CHECK SERIAL LOG",0xf800);return;}
    if(!esp_psram_is_initialized()) {std::printf("ERROR psram_missing\n");status_display::show("MEMORY ERROR","PSRAM NOT AVAILABLE",0xf800);return;}
    esp_err_t error=cameraInit();
    if(error!=ESP_OK) {std::printf("ERROR camera_init=%s\n",esp_err_to_name(error));status_display::show("CAMERA ERROR",esp_err_to_name(error),0xf800);return;}
    cameraOnline=true;
#ifdef CAMERA_DIAGNOSTIC
    // Explicit diagnostic build: bypass PIR, leave buzzer silent, keep RGB flash.
    std::printf("READY CAMERA_DIAGNOSTIC pir=BYPASSED buzzer=OFF camera_D3=GPIO12 capture_interval_ms=1500\n");
    unsigned diagnosticFrame=0;
    vTaskDelay(pdMS_TO_TICKS(1200));
    while(true) {
        auto fb=captureWithWhiteFlash();
        if(!fb) {
            std::printf("ERROR diagnostic_camera_capture check_D3_to_D12\n");
            vTaskDelay(pdMS_TO_TICKS(1500));continue;
        }
        const dl::image::jpeg_img_t jpeg{fb->buf,fb->len};
        auto decoded=dl::image::sw_decode_jpeg(jpeg,dl::image::DL_IMAGE_PIX_TYPE_RGB888);
        bool valid=decoded.data && decoded.width==320 && decoded.height==240;
        heap_caps_free(decoded.data);
        if(valid) {
            char metadata[384];
            std::snprintf(metadata,sizeof(metadata),"{\"frame\":%u,\"state\":\"CAMERA_TEST\",\"area_percent\":0,\"cutoff_percent\":5,\"bbox\":[0,0,0,0],\"grid\":[80,60],\"pir\":%d,\"jpeg_bytes\":%u,\"fnv1a\":\"%08lx\"}",++diagnosticFrame,gpio_get_level(GPIO_NUM_5),unsigned(fb->len),static_cast<unsigned long>(fnv1a(fb->buf,fb->len)));
    #ifdef VIBRATION_WIFI
        std::printf("DETECTION_SCORES frame=%u grayscale_percent=%.3f assisted_percent=%.3f color_enabled=%d grayscale_cutoff=7 color_cutoff=10\n",n,100.0*grayscaleRegion.area/N,100.0*assistedArea/N,int(colorAssist));
#endif
        std::printf("MOTION %s\n",metadata);
            transmitPhoto(diagnosticFrame,fb,metadata);
        } else std::printf("ERROR diagnostic_jpeg_decode check_D3_to_D12\n");
        esp_camera_fb_return(fb);
        vTaskDelay(pdMS_TO_TICKS(1500));
    }
#endif
    xTaskCreate(commandTask,"commands",3072,nullptr,3,nullptr);
#ifdef PIR_WIFI_CAMERA_TEST
    std::printf("READY PIR_WIFI_CAMERA_TEST wifi=ON vibration=BYPASSED speaker=OFF trigger=PIR_STABLE_HIGH_100ms rearm=LOW_500ms revision=20261118_review1\n");
#endif
    std::printf("READY clear_view_for_8_seconds_then_12_calibration_frames; commands=BASELINE,ARM; PIR_warmup=60_seconds\n");
    int64_t calibrateAfter=esp_timer_get_time()+8000000;
    const int64_t pirWarmupEnd=esp_timer_get_time()+60000000;
    int64_t cooldownUntil=0,lastHeartbeat=0;
    bool active=false,previousPir=true;
#ifdef VIBRATION_WIFI
    int64_t pirLowSince = 0, pirHighSince = 0;
    bool pirReady = false;
#endif
    unsigned burstFrames=0;
    unsigned consecutiveLargeFrames=0;
#ifdef VIBRATION_WIFI
    constexpr unsigned vibrationWindowSeconds = 10;
    constexpr int64_t vibrationWindowUs = vibrationWindowSeconds * 1000000LL;
    int64_t vibrationDeadline = 0;
#endif
    int64_t lastPhoto=0;
    unsigned n=0;
    while(true) {
        if (buzzerEnded.exchange(false)) {
            std::printf("DETERRENT_OFF count=%u\n", deterrentCount);
#ifdef VIBRATION_WIFI
            cooldownUntil = esp_timer_get_time() + 4500000;
            vibrationDeadline = 0;
            pirReady = false;
            pirLowSince = pirHighSince = 0;
            vibration::receivedMs.exchange(0);
            std::printf("COOLDOWN duration_ms=4500 reason=ALARM_FINISHED\n");
#endif
        }
        if (speakerTest.exchange(false)) {
            if (!active) {
                std::printf("SPEAKER_TEST requested=1\n");
                if (!soundDeterrent(0)) std::printf("ERROR speaker_test_timer\n");
            } else {
                std::printf("SPEAKER_TEST busy=camera; retry_after_capture=1\n");
            }
        }
        if(rearm.exchange(false)) {
            esp_timer_stop(buzzerTimer);silenceBuzzer(nullptr);
            active=false;cooldownUntil=0;growth.reset();
#ifdef VIBRATION_WIFI
            vibrationDeadline = 0;
            pirReady = false; pirLowSince = pirHighSince = 0;
#endif
            previousPir=gpio_get_level(GPIO_NUM_5);
            cameraStandby();
            std::printf("ARMED manual_rearm=1 pir=%d wait_for_LOW_then_HIGH=1\n",int(previousPir));
        }
        if(relearn.exchange(false)) {
            esp_timer_stop(buzzerTimer);silenceBuzzer(nullptr);
            active=false;cooldownUntil=0;
#ifdef VIBRATION_WIFI
            vibrationDeadline = 0;
            previousPir = gpio_get_level(GPIO_NUM_5);
#endif
            samples=0;growth.reset();std::memset(baseline,0,sizeof(baseline));
#ifdef VIBRATION_WIFI
            std::memset(baselineRgb,0,sizeof(baselineRgb));
            colorAssist=false;
#endif
            calibrateAfter=esp_timer_get_time()+3000000;
            std::printf("CALIBRATION clear_view_now; starts_in=3_seconds\n");
        }
        int64_t now=esp_timer_get_time();
        if(samples>=BASELINE_FRAMES && !active) {
            cameraStandby();
            bool high=gpio_get_level(GPIO_NUM_5);
            bool cooldownExpired=cooldownUntil && now>=cooldownUntil;
            if(cooldownExpired) cooldownUntil=0;
            xSemaphoreTake(buzzerMutex,portMAX_DELAY);
            bool sounding=buzzerTicks>=0;
            xSemaphoreGive(buzzerMutex);
            const char* waiting=now<pirWarmupEnd?"PIR_WARMUP":(sounding?"ALARM_ACTIVE":(cooldownUntil?"COOLDOWN":"ARMED"));
#ifdef VIBRATION_WIFI
            const bool canWait = now >= pirWarmupEnd && !sounding && !cooldownUntil;
            if (!canWait) vibration::receivedMs.exchange(0);
            if (!canWait || vibrationDeadline) {
                pirReady = false;
                pirLowSince = pirHighSince = 0;
            } else if (!high) {
                pirHighSince = 0;
                if (!pirLowSince) pirLowSince = now;
                if (now - pirLowSince >= 500000) pirReady = true;
            } else {
                pirLowSince = 0;
                if (!pirHighSince) pirHighSince = now;
            }
            const bool qualifiedPir = canWait && high && pirReady &&
                                      now - pirHighSince >= 100000;
            if (qualifiedPir) {
                pirReady = false;
                pirLowSince = pirHighSince = 0;
            }
#ifdef PIR_WIFI_CAMERA_TEST
            const bool startCapture = qualifiedPir;
            previousPir = high;
            if(startCapture) std::printf("PIR_TRIGGER test=PIR_WIFI_CAMERA starting_max_10_frames=1\n");
#else
            if (vibrationDeadline && now >= vibrationDeadline) {
                vibrationDeadline = 0;
                std::printf("VIBRATION_TIMEOUT camera=STANDBY\n");
            }
            if (qualifiedPir && !vibrationDeadline) {
                vibration::receivedMs.exchange(0);
                vibrationDeadline = now + vibrationWindowUs;
                std::printf("PIR_TRIGGER waiting_for_vibration_s=%u camera=STANDBY\n",
                            vibrationWindowSeconds);
            }
            if (!sounding) previousPir = high;
            if (vibrationDeadline)
                waiting = "WAIT_FOR_VIBRATION";
            const bool startCapture = canWait && vibrationDeadline && vibration::takeFreshEvent();
            if (startCapture) {
                vibrationDeadline = 0;
                std::printf("VIBRATION_RECEIVED starting_max_10_frames=1\n");
            }
#endif
#else
            const bool startCapture = now>=pirWarmupEnd && !sounding && !cooldownUntil &&
                                      high && (!previousPir || cooldownExpired);
#endif
            if(startCapture) {
                active=true;burstFrames=0;consecutiveLargeFrames=0;growth.reset();previousPir=true;
#ifndef VIBRATION_WIFI
                std::printf("PIR_TRIGGER starting_max_10_frames=1\n");
#endif
                status_display::show("PIR TRIGGER","WAKING CAMERA",0xffe0,deterrentCount);
            } else {
                // Require a fresh LOW after the alarm finishes before another trigger.
#ifndef VIBRATION_WIFI
                if(!sounding) previousPir=high;
#endif
                if(now-lastHeartbeat>=1000000) {
                    std::printf("STATUS state=%s pir=%d cooldown_s=%lld deterrents=%u camera=STANDBY\n",waiting,int(high),cooldownUntil?static_cast<long long>((cooldownUntil-now+999999)/1000000):0LL,deterrentCount);
                    char detail[40];
                    if(now<pirWarmupEnd) {
                        std::snprintf(detail,sizeof(detail),"%lld SECONDS LEFT",static_cast<long long>((pirWarmupEnd-now+999999)/1000000));
                        status_display::show("PIR WARMUP",detail,0xffe0,deterrentCount);
                    } else if(sounding) {
                        status_display::show("BUZZER ACTIVE","LARGE TARGET CONFIRMED",0xf800,deterrentCount);
                    } else if(cooldownUntil) {
                        std::snprintf(detail,sizeof(detail),"%lld SECONDS LEFT - PIR %s",static_cast<long long>((cooldownUntil-now+999999)/1000000),high?"HIGH":"LOW");
                        status_display::show("COOLDOWN",detail,0x07ff,deterrentCount);
                    } else {
                        status_display::show("ARMED",high?"PIR HIGH - WAITING FOR LOW":"PIR LOW - WAITING FOR MOTION",0x07e0,deterrentCount);
                    }
                    lastHeartbeat=now;
                }
                vTaskDelay(pdMS_TO_TICKS(50));continue;
            }
        }
        if(!cameraOnline) {
            if(cameraInit()!=ESP_OK) {
                std::printf("ERROR camera_wake; capture_aborted=1\n");
                active=false;cooldownUntil=0;previousPir=true;growth.reset();cameraStandby();
                vTaskDelay(pdMS_TO_TICKS(500));continue;
            }
            cameraOnline=true;
            vTaskDelay(pdMS_TO_TICKS(1200));
            for(int i=0;i<3;++i) {auto discard=esp_camera_fb_get();if(discard)esp_camera_fb_return(discard);vTaskDelay(pdMS_TO_TICKS(80));}
        }
        // Reference and detection photos use the same lighting to avoid
        // treating the new flash illumination itself as a foreground target.
        camera_fb_t* fb=captureWithWhiteFlash();
        if(!fb) {active=false;cooldownUntil=0;previousPir=true;growth.reset();cameraStandby();std::printf("ERROR camera_capture\n");vTaskDelay(pdMS_TO_TICKS(500));continue;}
        ++n;
        const dl::image::jpeg_img_t jpeg{fb->buf,fb->len};
        auto image=dl::image::sw_decode_jpeg(jpeg,dl::image::DL_IMAGE_PIX_TYPE_RGB888);
        if(!image.data || image.width!=320 || image.height!=240) {
            heap_caps_free(image.data);esp_camera_fb_return(fb);
            std::printf("ERROR jpeg_decode\n");
            consecutiveLargeFrames=0;
#ifdef VIBRATION_WIFI
            if(active && ++burstFrames<10) {
                vTaskDelay(pdMS_TO_TICKS(250));
                continue;
            }
            if(active) std::printf("BURST_END frames=%u large_confirmed=0 reason=JPEG_DECODE\n",burstFrames);
#endif
            active=false;cooldownUntil=0;previousPir=true;growth.reset();cameraStandby();
            vTaskDelay(pdMS_TO_TICKS(500));continue;
        }
        auto rgb=static_cast<uint8_t*>(image.data);
        for(int y=0;y<H;++y) for(int x=0;x<W;++x) {
            // Average each 4x4 block to reduce noise and high-frequency texture.
            unsigned sum=0;
#ifdef VIBRATION_WIFI
            unsigned channels[3]={};
#endif
            for(int dy=0;dy<4;++dy) for(int dx=0;dx<4;++dx) {
                size_t p=((y*4+dy)*320+x*4+dx)*3;
                sum+=(77*rgb[p]+150*rgb[p+1]+29*rgb[p+2])>>8;
#ifdef VIBRATION_WIFI
                for(int c=0;c<3;++c) channels[c]+=rgb[p+c];
#endif
            }
            gray[y*W+x]=sum/16;
#ifdef VIBRATION_WIFI
            for(int c=0;c<3;++c) blockRgb[y*W+x][c]=channels[c]/16;
#endif
        }
        heap_caps_free(image.data);
        const char* state="SETTLING";
        Region region;
#ifdef VIBRATION_WIFI
        Region grayscaleRegion;
        int assistedArea=0;
        bool qualified=false;
#endif
        int brightnessShift=0;
        bool fire=false;
        if(esp_timer_get_time()>=calibrateAfter) {
            if(samples<BASELINE_FRAMES) {
                for(int i=0;i<N;++i) baseline[i]+=gray[i];
#ifdef VIBRATION_WIFI
                for(int i=0;i<N;++i) for(int c=0;c<3;++c) baselineRgb[i][c]+=blockRgb[i][c];
#endif
                if(++samples==BASELINE_FRAMES) {
                    for(int i=0;i<N;++i) baseline[i]/=BASELINE_FRAMES;
#ifdef VIBRATION_WIFI
                    for(int i=0;i<N;++i) for(int c=0;c<3;++c) baselineRgb[i][c]/=BASELINE_FRAMES;
                    int darkBlocks=0;
                    for(int i=0;i<N;++i) darkBlocks+=baseline[i]<DARK_BLOCK_LEVEL;
                    colorAssist=darkBlocks*4>=N*3;
                    std::printf("DETECTION_MODE color_assist=%d dark_blocks_percent=%.1f grayscale_cutoff=7 color_cutoff=10\n",int(colorAssist),100.0*darkBlocks/N);
#endif
                    std::printf("CALIBRATION complete; baseline_fixed=1\n");
                }
                state="CALIBRATING";
            } else {
                // Median brightness offset suppresses uniform exposure shifts.
                int histogram[511]={};
                for(int i=0;i<N;++i) ++histogram[int(gray[i])-int(baseline[i])+255];
                int cumulative=0;
                for(int j=0;j<511;++j) {cumulative+=histogram[j];if(cumulative>=N/2){brightnessShift=j-255;break;}}
                for(int i=0;i<N;++i) {
                    int pixelDelta=PIXEL_DELTA;
                    mask[i]=std::abs(int(gray[i])-int(baseline[i])-brightnessShift)>=pixelDelta;
#ifdef VIBRATION_WIFI
                    grayscaleMask[i]=mask[i];
                    // A common RGB brightness offset cancels in this chroma range.
                    // Average blocks and require stronger color contrast than luma
                    // to avoid counting individual dark-frame color speckles.
                    int lo=255,hi=-255;
                    for(int c=0;c<3;++c) {
                        int delta=int(blockRgb[i][c])-int(baselineRgb[i][c]);
                        lo=std::min(lo,delta);hi=std::max(hi,delta);
                    }
                    int colorDelta=std::min(25,10+int(baseline[i])/4);
                    mask[i]=mask[i] || (colorAssist && hi-lo>=colorDelta);
#endif
                }
                region=largestRegion();
#ifdef VIBRATION_WIFI
                assistedArea=colorAssist?region.area:0;
                std::memcpy(mask,grayscaleMask,sizeof(mask));
                grayscaleRegion=largestRegion();
                bool grayscalePass=grayscaleRegion.area>=MIN_REGION_PIXELS;
                bool colorPass=colorAssist && assistedArea>=COLOR_REGION_PIXELS;
                bool big=grayscalePass || colorPass;
                qualified=big;
                if(grayscalePass || !colorPass) region=grayscaleRegion;
                consecutiveLargeFrames=big?consecutiveLargeFrames+1:0;
                fire=active && consecutiveLargeFrames>=2;
                state=fire?"LARGE_CHANGE":(big?"CONFIRMING":(region.area?"SMALL_CHANGE":"CLEAR"));
#else
                bool big=region.area>=MIN_REGION_PIXELS;
                bool approaching=growth.update(region);
                state=approaching?"LARGE_CHANGE":(big?"WAITING_FOR_GROWTH":(region.area?"SMALL_CHANGE":"CLEAR"));
                fire=active && approaching;
#endif
            }
        }
        if(active) ++burstFrames;
#ifdef PIR_WIFI_CAMERA_TEST
        fire=false;
#endif
        #ifdef PIR_WIFI_CAMERA_TEST
        if (std::strcmp(state, "LARGE_CHANGE") == 0) state = "LARGE_CHANGE_TEST_ONLY";
#endif
        if(fire && !soundDeterrent(n)) std::printf("ERROR deterrent_timer; buzzer_not_started=1\n");
        char displayDetail[48];
        std::snprintf(displayDetail,sizeof(displayDetail),"AREA %.1f%% - FRAME %u OF 10",100.0*region.area/N,burstFrames);
        if(fire) status_display::show("LARGE TARGET",displayDetail,0xf800,deterrentCount);
        else if(active) status_display::show(
#ifdef VIBRATION_WIFI
            qualified
#else
            region.area>=MIN_REGION_PIXELS
#endif
            ?"CONFIRMING":"SMALL / CLEAR",displayDetail,0xffe0,deterrentCount);
        else {
            std::snprintf(displayDetail,sizeof(displayDetail),"KEEP VIEW EMPTY - SAMPLE %d OF 12",samples);
            status_display::show(samples?"LEARNING VIEW":"CLEAR VIEW",displayDetail,0xffe0,deterrentCount);
        }
        char metadata[768];
#ifdef VIBRATION_WIFI
        std::snprintf(metadata, sizeof(metadata),
                      "{\"frame\":%u,\"state\":\"%s\",\"area_percent\":%.3f,\"cutoff_percent\":%.1f,\"changed_pixels\":%d,\"brightness_shift\":%d,\"bbox\":[%d,%d,%d,%d],\"grid\":[80,60],\"pir\":%d,\"baseline_samples\":%d,\"jpeg_bytes\":%u,\"fnv1a\":\"%08lx\"}",
                      n, state, 100.0*region.area/N, (colorAssist && grayscaleRegion.area<MIN_REGION_PIXELS && assistedArea>=COLOR_REGION_PIXELS)?10.0:7.0, region.area, brightnessShift,
                      region.x, region.y, region.w, region.h, gpio_get_level(GPIO_NUM_5),
                      samples, unsigned(fb->len), static_cast<unsigned long>(fnv1a(fb->buf, fb->len)));
#else
        std::snprintf(metadata,sizeof(metadata),"{\"frame\":%u,\"state\":\"%s\",\"area_percent\":%.3f,\"cutoff_percent\":10.0,\"growth_window\":5,\"growth_required_percent\":25,\"growth_min_gain_pixels\":96,\"growth_frames\":%d,\"growth_percent\":%d,\"growth_pixels\":%d,\"changed_pixels\":%d,\"brightness_shift\":%d,\"bbox\":[%d,%d,%d,%d],\"grid\":[80,60],\"pir\":%d,\"baseline_samples\":%d,\"jpeg_bytes\":%u,\"fnv1a\":\"%08lx\"}",n,state,100.0*region.area/N,growth.frames(),growth.gainPercent(),growth.gainPixels(),region.area,brightnessShift,region.x,region.y,region.w,region.h,gpio_get_level(GPIO_NUM_5),samples,unsigned(fb->len),static_cast<unsigned long>(fnv1a(fb->buf,fb->len)));
#endif
#ifdef VIBRATION_WIFI
        std::printf("DETECTION_SCORES frame=%u grayscale_percent=%.3f assisted_percent=%.3f color_enabled=%d grayscale_cutoff=7 color_cutoff=10\n",n,100.0*grayscaleRegion.area/N,100.0*assistedArea/N,int(colorAssist));
#endif
        std::printf("MOTION %s\n",metadata);
        if(active || esp_timer_get_time()-lastPhoto>=2000000) {
            transmitPhoto(n,fb,metadata);lastPhoto=esp_timer_get_time();
        }
        esp_camera_fb_return(fb);
        if(active && (fire || burstFrames>=10)) {
            std::printf("BURST_END frames=%u large_confirmed=%d\n",burstFrames,int(fire));
            active=false;growth.reset();
#ifdef VIBRATION_WIFI
            cooldownUntil=0;
#else
            cooldownUntil=fire?0:esp_timer_get_time()+120000000;
#endif
            previousPir=true;
            cameraStandby();
            if(fire) std::printf("CONFIRMED post_alarm_cooldown_ms=4500 wait_for_PIR_LOW=1 camera=STANDBY\n");
#ifdef VIBRATION_WIFI
            else std::printf("NO_CONFIRMED_TARGET cooldown_s=0 wait_for_PIR_LOW=1 camera=STANDBY\n");
#else
            else std::printf("COOLDOWN duration_s=120 reason=NO_CONFIRMED_TARGET camera=STANDBY\n");
#endif
        }
        vTaskDelay(pdMS_TO_TICKS(250));
    }
}

