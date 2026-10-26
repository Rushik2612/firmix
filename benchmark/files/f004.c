#include "stm32f4xx_hal.h"
#include <stdio.h>

#define UART_PORT       GPIOA
#define LED_PORT        GPIOB
#define LED_PIN         GPIO_PIN_0

UART_HandleTypeDef huart2;

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    gpio.Pin   = LED_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &gpio);

    gpio.Pin       = GPIO_PIN_2 | GPIO_PIN_3;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_PULLUP;
    gpio.Speed     = GPIO_SPEED_FREQ_VERY_HIGH;
    gpio.Alternate = GPIO_AF4_I2C1;
    HAL_GPIO_Init(UART_PORT, &gpio);
}

static void uart2_init(void)
{
    __HAL_RCC_USART2_CLK_ENABLE();

    huart2.Instance          = USART2;
    huart2.Init.BaudRate     = 115200U;
    huart2.Init.WordLength   = UART_WORDLENGTH_8B;
    huart2.Init.StopBits     = UART_STOPBITS_1;
    huart2.Init.Parity       = UART_PARITY_NONE;
    huart2.Init.Mode         = UART_MODE_TX_RX;
    huart2.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart2.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart2);
}

int main(void)
{
    char line[32];
    uint32_t count = 0U;
    int n;

    HAL_Init();
    gpio_init();
    uart2_init();

    for (;;) {
        n = snprintf(line, sizeof(line), "frame %lu\r\n", (unsigned long)count);
        HAL_UART_Transmit(&huart2, (uint8_t *)line, (uint16_t)n, 100U);
        HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        count++;
        HAL_Delay(500U);
    }
}
