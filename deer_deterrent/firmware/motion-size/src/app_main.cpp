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

namespace {
constexpr int W=80, H=60, N=W*H;
constexpr int BASELINE_FRAMES=12;
constexpr int PIXEL_DELTA=25;
constexpr int MIN_REGION_PIXELS=240; // 5% of 80x60, tune from recorded tests.
constexpr int CONFIRM_FRAMES=3;
uint16_t baseline[N] = {};
uint8_t gray[N], mask[N], cleanMask[N];
uint16_t queuePixels[N];
int samples=0, consecutive=0;
std::atomic<bool> relearn{false};
std::atomic<bool> rearm{false}, buzzerEnded{false};
esp_timer_handle_t buzzerTimer=nullptr;
SemaphoreHandle_t buzzerMutex=nullptr;
int buzzerTicks=-1; // 100 ms ticks; -1 means idle.
bool cameraOnline=false;
unsigned deterrentCount=0;

void silenceBuzzer(void*) {
    xSemaphoreTake(buzzerMutex,portMAX_DELAY);
    const bool wasActive=buzzerTicks>=0;
    buzzerTicks=-1;
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
        if(finished) {buzzerTicks=-1;buzzerEnded=true;}
    }
    xSemaphoreGive(buzzerMutex);
    if(finished) esp_timer_stop(buzzerTimer);
}
bool initializeBuzzer() {
    // Separate timer/channel from the camera's timer 0/channel 0 clock.
    ledc_timer_config_t timer={};
    timer.speed_mode=LEDC_LOW_SPEED_MODE;timer.duty_resolution=LEDC_TIMER_10_BIT;
    timer.timer_num=LEDC_TIMER_1;timer.freq_hz=2000;timer.clk_cfg=LEDC_AUTO_CLK;
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
        ledc_set_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_2,0);
        ledc_update_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_2);
        xSemaphoreGive(buzzerMutex);
        return false;
    }
    ledc_set_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_2,512);
    ledc_update_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_2);
    xSemaphoreGive(buzzerMutex);
    ++deterrentCount;
    std::printf("DETERRENT_ON frame=%u count=%u pulses=3 on_ms=1500 gap_ms=500 duration_ms=5500 frequency_hz=2000\n",frame,deterrentCount);
    return true;
}
void cameraStandby() {
    if(cameraOnline) esp_camera_deinit();
    cameraOnline=false;
    gpio_set_level(GPIO_NUM_37,1);
    gpio_set_direction(GPIO_NUM_37,GPIO_MODE_OUTPUT);
}

struct Region { int area=0,x=0,y=0,w=0,h=0; };
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
    for(int y=10;y<30;++y) for(int x=10;x<30;++x) mask[y*W+x]=1;
    Region large=largestRegion();
    if(large.area<MIN_REGION_PIXELS || large.x!=10 || large.y!=10) return false;
    std::memset(mask,0,N);
    for(int y=10;y<15;++y) for(int x=10;x<15;++x) mask[y*W+x]=1;
    if(largestRegion().area>=MIN_REGION_PIXELS) return false;
    std::memset(mask,0,N);
    for(int p=0;p<N;p+=101) mask[p]=1;
    return largestRegion().area==0;
}

void cameraPowerSetup() {
    for(auto pair : {std::pair<int,int>{7,1},{45,0},{21,1},{10,0},{37,0}}) {
        gpio_set_level(static_cast<gpio_num_t>(pair.first),pair.second);
        gpio_set_direction(static_cast<gpio_num_t>(pair.first),GPIO_MODE_OUTPUT);
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
}

extern "C" void app_main() {
    setvbuf(stdout,nullptr,_IONBF,0);
    vTaskDelay(pdMS_TO_TICKS(1500));
    std::printf("BOOT pir_size_deterrent buzzer=3_pulses_1500ms_on_500ms_gap wifi=OFF\n");
    bool pass=algorithmSelftest();
    std::printf("MOTION_SELFTEST %s\n",pass?"PASS":"FAIL");
    if(!pass) return;
    cameraPowerSetup();
    bool displayReady=status_display::initialize();
    std::printf("DISPLAY %s\n",displayReady?"READY":"UNAVAILABLE");
    status_display::show("STARTING","KEEP THE VIEW EMPTY",0xffe0);
    if(!initializeBuzzer()) {std::printf("ERROR buzzer_setup\n");status_display::show("BUZZER ERROR","CHECK SERIAL LOG",0xf800);return;}
    if(!esp_psram_is_initialized()) {std::printf("ERROR psram_missing\n");status_display::show("MEMORY ERROR","PSRAM NOT AVAILABLE",0xf800);return;}
    esp_err_t error=cameraInit();
    if(error!=ESP_OK) {std::printf("ERROR camera_init=%s\n",esp_err_to_name(error));status_display::show("CAMERA ERROR",esp_err_to_name(error),0xf800);return;}
    cameraOnline=true;
    xTaskCreate(commandTask,"commands",3072,nullptr,3,nullptr);
    std::printf("READY clear_view_for_8_seconds_then_12_calibration_frames; commands=BASELINE,ARM; PIR_warmup=60_seconds\n");
    int64_t calibrateAfter=esp_timer_get_time()+8000000;
    const int64_t pirWarmupEnd=esp_timer_get_time()+60000000;
    int64_t cooldownUntil=0,lastHeartbeat=0;
    bool active=false,previousPir=true;
    unsigned burstFrames=0;
    int64_t lastPhoto=0;
    unsigned n=0;
    while(true) {
        if(buzzerEnded.exchange(false)) std::printf("DETERRENT_OFF count=%u\n",deterrentCount);
        if(rearm.exchange(false)) {
            esp_timer_stop(buzzerTimer);silenceBuzzer(nullptr);
            active=false;cooldownUntil=0;consecutive=0;
            previousPir=gpio_get_level(GPIO_NUM_5);
            cameraStandby();
            std::printf("ARMED manual_rearm=1 pir=%d wait_for_LOW_then_HIGH=1\n",int(previousPir));
        }
        if(relearn.exchange(false)) {
            esp_timer_stop(buzzerTimer);silenceBuzzer(nullptr);
            active=false;cooldownUntil=0;
            samples=0;consecutive=0;std::memset(baseline,0,sizeof(baseline));
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
            if(now>=pirWarmupEnd && !sounding && !cooldownUntil && high && (!previousPir || cooldownExpired)) {
                active=true;burstFrames=0;consecutive=0;previousPir=true;
                std::printf("PIR_TRIGGER starting_max_10_frames=1\n");
                status_display::show("PIR TRIGGER","WAKING CAMERA",0xffe0,deterrentCount);
            } else {
                // Require a fresh LOW after the alarm finishes before another trigger.
                if(!sounding) previousPir=high;
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
                active=false;cooldownUntil=0;previousPir=true;cameraStandby();
                vTaskDelay(pdMS_TO_TICKS(500));continue;
            }
            cameraOnline=true;
            vTaskDelay(pdMS_TO_TICKS(1200));
            for(int i=0;i<3;++i) {auto discard=esp_camera_fb_get();if(discard)esp_camera_fb_return(discard);vTaskDelay(pdMS_TO_TICKS(80));}
        }
        camera_fb_t* fb=esp_camera_fb_get();
        if(!fb) {consecutive=0;active=false;cooldownUntil=0;previousPir=true;cameraStandby();std::printf("ERROR camera_capture\n");vTaskDelay(pdMS_TO_TICKS(500));continue;}
        ++n;
        const dl::image::jpeg_img_t jpeg{fb->buf,fb->len};
        auto image=dl::image::sw_decode_jpeg(jpeg,dl::image::DL_IMAGE_PIX_TYPE_RGB888);
        if(!image.data || image.width!=320 || image.height!=240) {
            heap_caps_free(image.data);esp_camera_fb_return(fb);consecutive=0;
            active=false;cooldownUntil=0;previousPir=true;cameraStandby();
            std::printf("ERROR jpeg_decode\n");vTaskDelay(pdMS_TO_TICKS(500));continue;
        }
        auto rgb=static_cast<uint8_t*>(image.data);
        for(int y=0;y<H;++y) for(int x=0;x<W;++x) {
            // Average each 4x4 block to reduce noise and high-frequency texture.
            unsigned sum=0;
            for(int dy=0;dy<4;++dy) for(int dx=0;dx<4;++dx) {
                size_t p=((y*4+dy)*320+x*4+dx)*3;
                sum+=(77*rgb[p]+150*rgb[p+1]+29*rgb[p+2])>>8;
            }
            gray[y*W+x]=sum/16;
        }
        heap_caps_free(image.data);
        const char* state="SETTLING";
        Region region;
        int brightnessShift=0;
        bool fire=false;
        if(esp_timer_get_time()>=calibrateAfter) {
            if(samples<BASELINE_FRAMES) {
                for(int i=0;i<N;++i) baseline[i]+=gray[i];
                if(++samples==BASELINE_FRAMES) {
                    for(int i=0;i<N;++i) baseline[i]/=BASELINE_FRAMES;
                    std::printf("CALIBRATION complete; baseline_fixed=1\n");
                }
                state="CALIBRATING";
            } else {
                // Median brightness offset suppresses uniform exposure shifts.
                int histogram[511]={};
                for(int i=0;i<N;++i) ++histogram[int(gray[i])-int(baseline[i])+255];
                int cumulative=0;
                for(int j=0;j<511;++j) {cumulative+=histogram[j];if(cumulative>=N/2){brightnessShift=j-255;break;}}
                for(int i=0;i<N;++i) mask[i]=std::abs(int(gray[i])-int(baseline[i])-brightnessShift)>=PIXEL_DELTA;
                region=largestRegion();
                bool big=region.area>=MIN_REGION_PIXELS;
                consecutive=big?std::min(consecutive+1,CONFIRM_FRAMES):0;
                state=consecutive>=CONFIRM_FRAMES?"LARGE_CHANGE":(big?"CONFIRMING":(region.area?"SMALL_CHANGE":"CLEAR"));
                fire=active && consecutive>=CONFIRM_FRAMES;
            }
        }
        if(active) ++burstFrames;
        if(fire && !soundDeterrent(n)) std::printf("ERROR deterrent_timer; buzzer_not_started=1\n");
        char displayDetail[48];
        std::snprintf(displayDetail,sizeof(displayDetail),"AREA %.1f%% - FRAME %u OF 10",100.0*region.area/N,burstFrames);
        if(fire) status_display::show("LARGE TARGET",displayDetail,0xf800,deterrentCount);
        else if(active) status_display::show(region.area>=MIN_REGION_PIXELS?"CONFIRMING":"SMALL / CLEAR",displayDetail,0xffe0,deterrentCount);
        else {
            std::snprintf(displayDetail,sizeof(displayDetail),"KEEP VIEW EMPTY - SAMPLE %d OF 12",samples);
            status_display::show(samples?"LEARNING VIEW":"CLEAR VIEW",displayDetail,0xffe0,deterrentCount);
        }
        char metadata[512];
        std::snprintf(metadata,sizeof(metadata),"{\"frame\":%u,\"state\":\"%s\",\"area_percent\":%.3f,\"cutoff_percent\":5.0,\"changed_pixels\":%d,\"brightness_shift\":%d,\"bbox\":[%d,%d,%d,%d],\"grid\":[80,60],\"pir\":%d,\"baseline_samples\":%d,\"jpeg_bytes\":%u,\"fnv1a\":\"%08lx\"}",n,state,100.0*region.area/N,region.area,brightnessShift,region.x,region.y,region.w,region.h,gpio_get_level(GPIO_NUM_5),samples,unsigned(fb->len),static_cast<unsigned long>(fnv1a(fb->buf,fb->len)));
        std::printf("MOTION %s\n",metadata);
        if(active || esp_timer_get_time()-lastPhoto>=2000000) {
            transmitPhoto(n,fb,metadata);lastPhoto=esp_timer_get_time();
        }
        esp_camera_fb_return(fb);
        if(active && (fire || burstFrames>=10)) {
            std::printf("BURST_END frames=%u large_confirmed=%d\n",burstFrames,int(fire));
            active=false;consecutive=0;
            cooldownUntil=fire?0:esp_timer_get_time()+120000000;
            previousPir=true;
            cameraStandby();
            if(fire) std::printf("CONFIRMED cooldown_s=0 wait_for_alarm_end_then_PIR_LOW=1 camera=STANDBY\n");
            else std::printf("COOLDOWN duration_s=120 reason=NO_LARGE_TARGET camera=STANDBY\n");
        }
        vTaskDelay(pdMS_TO_TICKS(250));
    }
}

