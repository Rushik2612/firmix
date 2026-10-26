#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"

#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define RX_QUEUE_LEN    16U

UART_HandleTypeDef huart2;

static QueueHandle_t rx_queue;
static uint8_t rx_byte;

static void uart2_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_USART2_CLK_ENABLE();

    gpio.Pin       = GPIO_PIN_2 | GPIO_PIN_3;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_PULLUP;
    gpio.Speed     = GPIO_SPEED_FREQ_VERY_HIGH;
    gpio.Alternate = GPIO_AF7_USART2;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin       = LED_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_LOW;
    gpio.Alternate = 0U;
    HAL_GPIO_Init(LED_PORT, &gpio);

    huart2.Instance          = USART2;
    huart2.Init.BaudRate     = 115200U;
    huart2.Init.WordLength   = UART_WORDLENGTH_8B;
    huart2.Init.StopBits     = UART_STOPBITS_1;
    huart2.Init.Parity       = UART_PARITY_NONE;
    huart2.Init.Mode         = UART_MODE_TX_RX;
    huart2.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart2.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart2);

    HAL_NVIC_SetPriority(USART2_IRQn, 2, 0);
    HAL_NVIC_EnableIRQ(USART2_IRQn);
}

void USART2_IRQHandler(void)
{
    HAL_UART_IRQHandler(&huart2);
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    BaseType_t woken = pdFALSE;

    if (huart->Instance == USART2) {
        xQueueSendFromISR(rx_queue, &rx_byte, &woken);
        HAL_UART_Receive_IT(&huart2, &rx_byte, 1U);
    }
    portYIELD_FROM_ISR(woken);
}

static void parser_task(void *arg)
{
    uint8_t b;

    (void)arg;

    for (;;) {
        if (xQueueReceive(rx_queue, &b, portMAX_DELAY) == pdTRUE) {
            if (b == 't') {
                HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
            }
        }
    }
}

int main(void)
{
    HAL_Init();

    rx_queue = xQueueCreate(RX_QUEUE_LEN, sizeof(uint8_t));
    uart2_init();
    HAL_UART_Receive_IT(&huart2, &rx_byte, 1U);

    xTaskCreate(parser_task, "parser", 128, NULL, 2, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
