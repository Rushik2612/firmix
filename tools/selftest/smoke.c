/* dev_smoke.c -- toolchain smoke test (not a benchmark file, no bug seeded).
 * Confirms HAL + FreeRTOS headers resolve and compile for STM32F411. */
#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"
#include "queue.h"

static SemaphoreHandle_t g_lock;

static void blink_task(void *arg)
{
    (void)arg;
    for (;;) {
        if (xSemaphoreTake(g_lock, portMAX_DELAY) == pdTRUE) {
            HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_5);
            xSemaphoreGive(g_lock);
        }
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

int main(void)
{
    HAL_Init();
    __HAL_RCC_GPIOA_CLK_ENABLE();
    GPIO_InitTypeDef gpio = {0};
    gpio.Pin = GPIO_PIN_5;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    HAL_GPIO_Init(GPIOA, &gpio);
    g_lock = xSemaphoreCreateMutex();
    xTaskCreate(blink_task, "blink", 128, NULL, 2, NULL);
    vTaskStartScheduler();
    for (;;) { }
}
