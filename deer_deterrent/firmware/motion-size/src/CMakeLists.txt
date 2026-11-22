idf_component_register(SRCS "app_main.cpp" INCLUDE_DIRS "."
                       PRIV_REQUIRES esp_timer esp_psram driver mbedtls esp_lcd
                                     esp_event esp_netif esp_wifi esp_http_server)

