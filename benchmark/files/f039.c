#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"

#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define LINE_QUEUE_LEN  24U

UART_HandleTypeDef huart1;

static QueueHandle_t line_queue;
static uint8_t rx_byte;

static void uart1_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_USART1_CLK_ENABLE();

    gpio.Pin       = GPIO_PIN_9 | GPIO_PIN_10;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_PULLUP;
    gpio.Speed     = GPIO_SPEED_FREQ_VERY_HIGH;
    gpio.Alternate = GPIO_AF7_USART1;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin       = LED_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_LOW;
    gpio.Alternate = 0U;
    HAL_GPIO_Init(LED_PORT, &gpio);

    huart1.Instance          = USART1;
    huart1.Init.BaudRate     = 921600U;
    huart1.Init.WordLength   = UART_WORDLENGTH_8B;
    huart1.Init.StopBits     = UART_STOPBITS_1;
    huart1.Init.Parity       = UART_PARITY_NONE;
    huart1.Init.Mode         = UART_MODE_RX;
    huart1.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart1);

    HAL_NVIC_SetPriority(USART1_IRQn, 3, 1);
    HAL_NVIC_EnableIRQ(USART1_IRQn);
}

void USART1_IRQHandler(void)
{
    HAL_UART_IRQHandler(&huart1);
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    BaseType_t woken = pdFALSE;

    if (huart->Instance == USART1) {
        xQueueSendToBackFromISR(line_queue, &rx_byte, &woken);
        HAL_UART_Receive_IT(&huart1, &rx_byte, 1U);
    }
    portYIELD_FROM_ISR(woken);
}

static void line_task(void *arg)
{
    uint8_t c;
    uint32_t count = 0U;

    (void)arg;

    for (;;) {
        if (xQueueReceive(line_queue, &c, portMAX_DELAY) == pdTRUE) {
            count++;
            if (c == '\n') {
                HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
                count = 0U;
            }
        }
    }
}

int main(void)
{
    HAL_Init();

    line_queue = xQueueCreate(LINE_QUEUE_LEN, sizeof(uint8_t));
    uart1_init();
    HAL_UART_Receive_IT(&huart1, &rx_byte, 1U);

    xTaskCreate(line_task, "line", 128, NULL, 2, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
