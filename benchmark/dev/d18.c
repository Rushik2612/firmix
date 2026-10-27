#include "stm32f4xx_hal.h"
#include <stdio.h>

#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define REPORT_PERIOD   500U

UART_HandleTypeDef huart2;

static volatile uint8_t tx_done;

static void uart2_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_USART2_CLK_ENABLE();

    gpio.Pin       = GPIO_PIN_2 | GPIO_PIN_3;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_PULLUP;
    gpio.Speed     = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF7_USART2;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin       = LED_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Pull      = GPIO_NOPULL;
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

    HAL_NVIC_SetPriority(USART2_IRQn, 6, 0);
    HAL_NVIC_EnableIRQ(USART2_IRQn);
}

void USART2_IRQHandler(void)
{
    HAL_UART_IRQHandler(&huart2);
}

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART2) {
        tx_done = 1U;
    }
}

static int report_uptime(uint32_t ms)
{
    char line[32];
    int n = snprintf(line, sizeof(line), "up=%lu\r\n", (unsigned long)ms);

    if ((n <= 0) || (n >= (int)sizeof(line))) {
        return -1;
    }
    tx_done = 0U;
    if (HAL_UART_Transmit_IT(&huart2, (uint8_t *)line, (uint16_t)n) != HAL_OK) {
        return -2;
    }
    while (tx_done == 0U) {
    }
    return 0;
}

int main(void)
{
    HAL_Init();
    uart2_init();

    for (;;) {
        if (report_uptime(HAL_GetTick()) == 0) {
            HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        }
        HAL_Delay(REPORT_PERIOD);
    }
}
