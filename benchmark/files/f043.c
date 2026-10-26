#include "stm32f4xx_hal.h"
#include <stdio.h>

#define LED_PORT        GPIOB
#define LED_PIN         GPIO_PIN_1

UART_HandleTypeDef huart1;

static void uart1_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_USART1_CLK_ENABLE();

    gpio.Pin       = GPIO_PIN_9;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_VERY_HIGH;
    gpio.Alternate = GPIO_AF7_USART1;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin       = LED_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Speed     = GPIO_SPEED_FREQ_LOW;
    gpio.Alternate = 0U;
    HAL_GPIO_Init(LED_PORT, &gpio);

    huart1.Instance          = USART1;
    huart1.Init.BaudRate     = 9600U;
    huart1.Init.WordLength   = UART_WORDLENGTH_8B;
    huart1.Init.StopBits     = UART_STOPBITS_1;
    huart1.Init.Parity       = UART_PARITY_NONE;
    huart1.Init.Mode         = UART_MODE_TX;
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

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1) {
        HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
    }
}

static void report_reading(uint32_t reading)
{
    char line[40];
    int n;

    n = snprintf(line, sizeof(line), "reading=%lu units, ok\r\n", (unsigned long)reading);
    HAL_UART_Transmit_IT(&huart1, (uint8_t *)line, (uint16_t)n);
    HAL_Delay(5U);
}

int main(void)
{
    uint32_t reading = 0U;

    HAL_Init();
    uart1_init();

    for (;;) {
        report_reading(reading);
        reading += 7U;
        HAL_Delay(1000U);
    }
}
