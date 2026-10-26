#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"

#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define RX_QUEUE_LEN    32U

UART_HandleTypeDef huart1;

static QueueHandle_t rx_queue;
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
    huart1.Init.BaudRate     = 115200U;
    huart1.Init.WordLength   = UART_WORDLENGTH_8B;
    huart1.Init.StopBits     = UART_STOPBITS_1;
    huart1.Init.Parity       = UART_PARITY_NONE;
    huart1.Init.Mode         = UART_MODE_RX;
    huart1.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart1);

    HAL_NVIC_SetPriority(USART1_IRQn, 7, 0);
    HAL_NVIC_EnableIRQ(USART1_IRQn);
}

void USART1_IRQHandler(void)
{
    HAL_UART_IRQHandler(&huart1);
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1) {
        xQueueSend(rx_queue, &rx_byte, 0);
        HAL_UART_Receive_IT(&huart1, &rx_byte, 1U);
    }
}

static void command_task(void *arg)
{
    uint8_t c;

    (void)arg;

    for (;;) {
        if (xQueueReceive(rx_queue, &c, portMAX_DELAY) == pdTRUE) {
            if (c == 'l') {
                HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
            }
        }
    }
}

int main(void)
{
    HAL_Init();

    rx_queue = xQueueCreate(RX_QUEUE_LEN, sizeof(uint8_t));
    uart1_init();
    HAL_UART_Receive_IT(&huart1, &rx_byte, 1U);

    xTaskCreate(command_task, "cmd", 128, NULL, 2, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
