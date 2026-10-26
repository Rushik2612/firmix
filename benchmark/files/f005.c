#include "stm32f4xx_hal.h"
#include <stdio.h>

#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5

UART_HandleTypeDef huart6;

static volatile uint8_t tx_done;

static void uart6_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_USART6_CLK_ENABLE();

    gpio.Pin       = GPIO_PIN_11;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF8_USART6;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin       = LED_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Speed     = GPIO_SPEED_FREQ_LOW;
    gpio.Alternate = 0U;
    HAL_GPIO_Init(LED_PORT, &gpio);

    huart6.Instance          = USART6;
    huart6.Init.BaudRate     = 19200U;
    huart6.Init.WordLength   = UART_WORDLENGTH_8B;
    huart6.Init.StopBits     = UART_STOPBITS_1;
    huart6.Init.Parity       = UART_PARITY_NONE;
    huart6.Init.Mode         = UART_MODE_TX;
    huart6.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart6.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart6);

    HAL_NVIC_SetPriority(USART6_IRQn, 6, 0);
    HAL_NVIC_EnableIRQ(USART6_IRQn);
}

void USART6_IRQHandler(void)
{
    HAL_UART_IRQHandler(&huart6);
}

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART6) {
        tx_done = 1U;
    }
}

static void send_value(uint32_t value)
{
    char line[40];
    int n;

    n = snprintf(line, sizeof(line), "value=%lu\r\n", (unsigned long)value);

    tx_done = 0U;
    HAL_UART_Transmit_IT(&huart6, (uint8_t *)line, (uint16_t)n);

    while (tx_done == 0U) {
    }
}

int main(void)
{
    uint32_t value = 0U;

    HAL_Init();
    uart6_init();

    for (;;) {
        send_value(value);
        value += 3U;
        HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        HAL_Delay(500U);
    }
}
