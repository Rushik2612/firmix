#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"
#include <string.h>

#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5

UART_HandleTypeDef huart2;

static SemaphoreHandle_t console_mutex;

static void uart2_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_USART2_CLK_ENABLE();

    gpio.Pin       = GPIO_PIN_2;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_VERY_HIGH;
    gpio.Alternate = GPIO_AF7_USART2;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin       = LED_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Speed     = GPIO_SPEED_FREQ_LOW;
    gpio.Alternate = 0U;
    HAL_GPIO_Init(LED_PORT, &gpio);

    huart2.Instance          = USART2;
    huart2.Init.BaudRate     = 115200U;
    huart2.Init.WordLength   = UART_WORDLENGTH_8B;
    huart2.Init.StopBits     = UART_STOPBITS_1;
    huart2.Init.Parity       = UART_PARITY_NONE;
    huart2.Init.Mode         = UART_MODE_TX;
    huart2.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart2.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart2);
}

static void console_print(const char *text)
{
    HAL_UART_Transmit(&huart2, (uint8_t *)text, (uint16_t)strlen(text), 50U);
}

static void report_status(uint8_t level)
{
    if (xSemaphoreTake(console_mutex, pdMS_TO_TICKS(50)) != pdTRUE) {
        return;
    }

    if (level == 0U) {
        return;
    }

    console_print("status: level ");
    console_print((level > 5U) ? "high\r\n" : "ok\r\n");

    xSemaphoreGive(console_mutex);
}

static void monitor_task(void *arg)
{
    uint8_t level = 0U;

    (void)arg;

    for (;;) {
        report_status(level);
        level = (uint8_t)((level + 1U) % 8U);
        HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        vTaskDelay(pdMS_TO_TICKS(300));
    }
}

static void banner_task(void *arg)
{
    (void)arg;

    for (;;) {
        if (xSemaphoreTake(console_mutex, pdMS_TO_TICKS(50)) == pdTRUE) {
            console_print("alive\r\n");
            xSemaphoreGive(console_mutex);
        }
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

int main(void)
{
    HAL_Init();
    uart2_init();

    console_mutex = xSemaphoreCreateMutex();

    xTaskCreate(monitor_task, "monitor", 192, NULL, 2, NULL);
    xTaskCreate(banner_task, "banner", 192, NULL, 1, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
