#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"
#include <string.h>

#define LED_PORT            GPIOB
#define LED_PIN             GPIO_PIN_0
#define SETTINGS_VERSION    3U
#define SETTINGS_NAME_LEN   16U

typedef struct {
    uint8_t  version;
    uint8_t  brightness;
    uint16_t blink_ms;
    char     name[SETTINGS_NAME_LEN];
    uint32_t checksum;
} settings_t;

static SemaphoreHandle_t settings_mutex;
static settings_t stored;

static uint32_t checksum_of(const settings_t *s)
{
    const uint8_t *p = (const uint8_t *)s;
    uint32_t sum = 0U;
    size_t i;

    for (i = 0U; i < offsetof(settings_t, checksum); i++) {
        sum = (sum << 1) ^ p[i];
    }
    return sum;
}

static int settings_save(const settings_t *s)
{
    if (xSemaphoreTake(settings_mutex, pdMS_TO_TICKS(100)) != pdTRUE) {
        return -1;
    }

    if (s->version != SETTINGS_VERSION) {
        goto reject;
    }

    if (checksum_of(s) != s->checksum) {
        goto reject;
    }

    memcpy(&stored, s, sizeof(stored));
    xSemaphoreGive(settings_mutex);
    return 0;

reject:
    return -2;
}

static int settings_load(settings_t *out)
{
    if (xSemaphoreTake(settings_mutex, pdMS_TO_TICKS(100)) != pdTRUE) {
        return -1;
    }

    memcpy(out, &stored, sizeof(*out));
    xSemaphoreGive(settings_mutex);
    return 0;
}

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOB_CLK_ENABLE();

    gpio.Pin   = LED_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &gpio);
}

static void config_task(void *arg)
{
    settings_t next = { SETTINGS_VERSION, 80U, 500U, "unit-a", 0U };
    uint16_t round = 0U;

    (void)arg;

    for (;;) {
        next.blink_ms = (uint16_t)(200U + (round % 4U) * 100U);
        next.version  = (round % 5U == 4U) ? 2U : SETTINGS_VERSION;
        next.checksum = checksum_of(&next);
        (void)settings_save(&next);
        round++;
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

static void blink_task(void *arg)
{
    settings_t cfg;

    (void)arg;

    for (;;) {
        if (settings_load(&cfg) == 0 && cfg.blink_ms != 0U) {
            HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
            vTaskDelay(pdMS_TO_TICKS(cfg.blink_ms));
        } else {
            vTaskDelay(pdMS_TO_TICKS(100));
        }
    }
}

int main(void)
{
    HAL_Init();
    gpio_init();

    settings_mutex = xSemaphoreCreateMutex();

    xTaskCreate(config_task, "config", 192, NULL, 1, NULL);
    xTaskCreate(blink_task, "blink", 192, NULL, 2, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
