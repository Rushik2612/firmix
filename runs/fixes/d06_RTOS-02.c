#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"
#include <string.h>

#define LOG_MAX_LEN         48U
#define LOG_ERR_BUSY        (-1)
#define LOG_ERR_TOO_LONG    (-2)
#define LOG_ERR_TX          (-3)

UART_HandleTypeDef huart2;

static SemaphoreHandle_t uart_mutex;

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

static int log_write(const char *msg)
{
    size_t len = strlen(msg);

    if (xSemaphoreTake(uart_mutex, pdMS_TO_TICKS(50)) != pdTRUE) {
        return LOG_ERR_BUSY;
    }

    if (len > LOG_MAX_LEN) {
    xSemaphoreGive(uart_mutex);
    return LOG_ERR_TOO_LONG;
    }

    if (HAL_UART_Transmit(&huart2, (uint8_t *)msg, (uint16_t)len, 100U) != HAL_OK) {
        xSemaphoreGive(uart_mutex);
        return LOG_ERR_TX;
    }

    xSemaphoreGive(uart_mutex);
    return 0;
}

static void sensor_task(void *arg)
{
    (void)arg;

    for (;;) {
        (void)log_write("sensor: ok\r\n");
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

static void diag_task(void *arg)
{
    (void)arg;

    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(60000));
        (void)log_write("diag: full status dump follows, see attached counters and flags\r\n");
    }
}

int main(void)
{
    HAL_Init();
    uart2_init();

    uart_mutex = xSemaphoreCreateMutex();

    xTaskCreate(sensor_task, "sensor", 256, NULL, 2, NULL);
    xTaskCreate(diag_task, "diag", 256, NULL, 1, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
