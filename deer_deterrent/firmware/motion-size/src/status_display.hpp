#pragma once
#include <algorithm>
#include <cctype>
#include <cstdio>
#include <cstring>
#include "driver/spi_master.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_panel_vendor.h"
#include "esp_heap_caps.h"
#include "freertos/semphr.h"

namespace status_display {
constexpr int width=240,height=135;
static esp_lcd_panel_handle_t panel=nullptr;
static SemaphoreHandle_t transferDone=nullptr;
static uint16_t* pixels=nullptr;
static bool enabled=false;
static const uint8_t letters[][5]={
{0x7e,0x11,0x11,0x11,0x7e},{0x7f,0x49,0x49,0x49,0x36},{0x3e,0x41,0x41,0x41,0x22},
{0x7f,0x41,0x41,0x22,0x1c},{0x7f,0x49,0x49,0x49,0x41},{0x7f,0x09,0x09,0x09,0x01},
{0x3e,0x41,0x49,0x49,0x7a},{0x7f,0x08,0x08,0x08,0x7f},{0,0x41,0x7f,0x41,0},
{0x20,0x40,0x41,0x3f,0x01},{0x7f,0x08,0x14,0x22,0x41},{0x7f,0x40,0x40,0x40,0x40},
{0x7f,0x02,0x0c,0x02,0x7f},{0x7f,0x04,0x08,0x10,0x7f},{0x3e,0x41,0x41,0x41,0x3e},
{0x7f,0x09,0x09,0x09,0x06},{0x3e,0x41,0x51,0x21,0x5e},{0x7f,0x09,0x19,0x29,0x46},
{0x46,0x49,0x49,0x49,0x31},{0x01,0x01,0x7f,0x01,0x01},{0x3f,0x40,0x40,0x40,0x3f},
{0x1f,0x20,0x40,0x20,0x1f},{0x3f,0x40,0x38,0x40,0x3f},{0x63,0x14,0x08,0x14,0x63},
{0x07,0x08,0x70,0x08,0x07},{0x61,0x51,0x49,0x45,0x43}};
static const uint8_t digits[][5]={
{0x3e,0x51,0x49,0x45,0x3e},{0,0x42,0x7f,0x40,0},{0x42,0x61,0x51,0x49,0x46},
{0x21,0x41,0x45,0x4b,0x31},{0x18,0x14,0x12,0x7f,0x10},{0x27,0x45,0x45,0x45,0x39},
{0x3c,0x4a,0x49,0x49,0x30},{0x01,0x71,0x09,0x05,0x03},{0x36,0x49,0x49,0x49,0x36},
{0x06,0x49,0x49,0x29,0x1e}};
inline uint8_t column(char c,int x) {
    c=static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    if(c>='A'&&c<='Z') return letters[c-'A'][x];
    if(c>='0'&&c<='9') return digits[c-'0'][x];
    if(c=='.') return x==2?0x60:0;
    if(c==':') return x==2?0x36:0;
    if(c=='-'||c=='_') return c=='-'?0x08:0x40;
    if(c=='%') {const uint8_t p[]={0x63,0x13,0x08,0x64,0x63};return p[x];}
    if(c=='/') {const uint8_t p[]={0x20,0x10,0x08,0x04,0x02};return p[x];}
    return 0;
}
inline void text(int x,int y,const char* value,int scale,uint16_t color) {
    const uint16_t swapped=(color>>8)|(color<<8);
    for(;*value && x+6*scale<=width;++value,x+=6*scale) {
        for(int cx=0;cx<5;++cx) for(int cy=0;cy<7;++cy) if(column(*value,cx)&(1<<cy))
            for(int dx=0;dx<scale;++dx) for(int dy=0;dy<scale;++dy) {
                int px=x+cx*scale+dx,py=y+cy*scale+dy;
                if(px>=0&&px<width&&py>=0&&py<height) pixels[py*width+px]=swapped;
            }
    }
}
inline bool completed(esp_lcd_panel_io_handle_t,esp_lcd_panel_io_event_data_t*,void*) {
    BaseType_t wake=pdFALSE;
    xSemaphoreGiveFromISR(transferDone,&wake);
    return wake==pdTRUE;
}
inline bool initialize() {
    transferDone=xSemaphoreCreateBinary();
    pixels=static_cast<uint16_t*>(heap_caps_malloc(width*height*2,MALLOC_CAP_DMA|MALLOC_CAP_INTERNAL));
    if(!pixels||!transferDone) return false;
    spi_bus_config_t bus={};
    bus.mosi_io_num=35;bus.miso_io_num=-1;bus.sclk_io_num=36;
    bus.quadwp_io_num=-1;bus.quadhd_io_num=-1;bus.max_transfer_sz=width*height*2;
    if(spi_bus_initialize(SPI3_HOST,&bus,SPI_DMA_CH_AUTO)!=ESP_OK) return false;
    esp_lcd_panel_io_spi_config_t ioConfig={};
    ioConfig.cs_gpio_num=7;ioConfig.dc_gpio_num=39;ioConfig.spi_mode=0;
    ioConfig.pclk_hz=20000000;ioConfig.trans_queue_depth=1;
    ioConfig.lcd_cmd_bits=8;ioConfig.lcd_param_bits=8;ioConfig.on_color_trans_done=completed;
    esp_lcd_panel_io_handle_t io=nullptr;
    if(esp_lcd_new_panel_io_spi(SPI3_HOST,&ioConfig,&io)!=ESP_OK) return false;
    esp_lcd_panel_dev_config_t device={};
    device.reset_gpio_num=40;device.rgb_ele_order=LCD_RGB_ELEMENT_ORDER_RGB;device.bits_per_pixel=16;
    if(esp_lcd_new_panel_st7789(io,&device,&panel)!=ESP_OK) return false;
    if(esp_lcd_panel_reset(panel)!=ESP_OK || esp_lcd_panel_init(panel)!=ESP_OK) return false;
    // Match Adafruit 135x240 ST7789 rotation 3 (240x135 landscape).
    if(esp_lcd_panel_swap_xy(panel,true)!=ESP_OK || esp_lcd_panel_mirror(panel,false,true)!=ESP_OK ||
       esp_lcd_panel_set_gap(panel,40,53)!=ESP_OK || esp_lcd_panel_invert_color(panel,true)!=ESP_OK ||
       esp_lcd_panel_disp_on_off(panel,true)!=ESP_OK) return false;
    gpio_set_level(GPIO_NUM_45,1);
    enabled=true;
    return true;
}
inline void show(const char* state,const char* detail,uint16_t color=0x07e0,unsigned alarms=0) {
    if(!enabled) return;
    std::memset(pixels,0,width*height*2);
    text(6,6,"PIR SIZE DETECTOR",1,0xffff);
    text(6,27,state,2,color);
    text(6,56,detail,1,0xffff);
    text(6,76,"CUTOFF: 5% / 3 FRAMES",1,0xffff);
    char line[36];std::snprintf(line,sizeof(line),"DETERRENT EVENTS: %u",alarms);
    text(6,94,line,1,0xffff);
    text(6,116,"BUZZER: 3 X 1.5S",1,0xffff);
    xSemaphoreTake(transferDone,0);
    if(esp_lcd_panel_draw_bitmap(panel,0,0,width,height,pixels)!=ESP_OK ||
       xSemaphoreTake(transferDone,pdMS_TO_TICKS(1000))!=pdTRUE) {
        // Stop drawing rather than modify a buffer still owned by DMA.
        enabled=false;std::printf("DISPLAY transfer_failed; serial_test_continues=1\n");
    }
}
}
