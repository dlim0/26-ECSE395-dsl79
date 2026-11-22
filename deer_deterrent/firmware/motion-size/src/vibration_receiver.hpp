#pragma once
#include <atomic>
#include <cstring>
#include "esp_event.h"
#include "esp_http_server.h"
#include "esp_netif.h"
#include "esp_timer.h"
#include "esp_wifi.h"

namespace vibration {
constexpr char ssid[] = "Feeder-Main";
constexpr char password[] = "FeederBench26"; // Local prototype access point.
constexpr uint32_t freshnessMs = 2000;
inline std::atomic<uint32_t> receivedMs{0};

inline esp_err_t receive(httpd_req_t* request) {
    char body[9];
    if (request->content_len != sizeof(body)) {
        return httpd_resp_send_err(request, HTTPD_400_BAD_REQUEST, "Expected vibration");
    }
    size_t offset = 0;
    while (offset < sizeof(body)) {
        const int count = httpd_req_recv(request, body + offset, sizeof(body) - offset);
        if (count <= 0) return ESP_FAIL;
        offset += count;
    }
    if (std::memcmp(body, "vibration", sizeof(body)) != 0) {
        return httpd_resp_send_err(request, HTTPD_400_BAD_REQUEST, "Expected vibration");
    }
    receivedMs.store(static_cast<uint32_t>(esp_timer_get_time() / 1000));
    return httpd_resp_sendstr(request, "received");
}

inline bool takeFreshEvent() {
    const uint32_t event = receivedMs.exchange(0);
    const auto now = static_cast<uint32_t>(esp_timer_get_time() / 1000);
    return event && now - event <= freshnessMs;
}

inline esp_err_t start() {
    auto result = esp_netif_init();
    if (result != ESP_OK) return result;
    result = esp_event_loop_create_default();
    if (result != ESP_OK) return result;
    if (!esp_netif_create_default_wifi_ap()) return ESP_FAIL;
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    init.nvs_enable = false;
    if ((result = esp_wifi_init(&init)) != ESP_OK) return result;
    if ((result = esp_wifi_set_storage(WIFI_STORAGE_RAM)) != ESP_OK) return result;
    if ((result = esp_wifi_set_mode(WIFI_MODE_AP)) != ESP_OK) return result;
    wifi_config_t config{};
    std::memcpy(config.ap.ssid, ssid, sizeof(ssid));
    std::memcpy(config.ap.password, password, sizeof(password));
    config.ap.channel = 1;
    config.ap.max_connection = 2;
    config.ap.authmode = WIFI_AUTH_WPA2_PSK;
    if ((result = esp_wifi_set_config(WIFI_IF_AP, &config)) != ESP_OK) return result;
    if ((result = esp_wifi_start()) != ESP_OK) return result;
    httpd_config_t http = HTTPD_DEFAULT_CONFIG();
    httpd_handle_t server = nullptr;
    if ((result = httpd_start(&server, &http)) != ESP_OK) return result;
    httpd_uri_t endpoint{};
    endpoint.uri = "/vibration";
    endpoint.method = HTTP_POST;
    endpoint.handler = receive;
    return httpd_register_uri_handler(server, &endpoint);
}
}
