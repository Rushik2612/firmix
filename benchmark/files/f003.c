#include "stm32f4xx_hal.h"

#define STATUS_PORT     GPIOC
#define STATUS_PIN      GPIO_PIN_13
#define SENSE_PORT      GPIOA
#define SENSE_PIN       GPIO_PIN_0

UART_HandleTypeDef huart2;

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();

    gpio.Pin   = SENSE_PIN;
    gpio.Mode  = GPIO_MODE_INPUT;
    gpio.Pull  = GPIO_PULLDOWN;
    HAL_GPIO_Init(SENSE_PORT, &gpio);

    gpio.Pin   = STATUS_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(STATUS_PORT, &gpio);
}

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

int main(void)
{
    static uint8_t on_msg[]  = "sense: high\r\n";
    static uint8_t off_msg[] = "sense: low\r\n";

    HAL_Init();
    gpio_init();
    uart2_init();

    for (;;) {
        if (HAL_GPIO_ReadPin(SENSE_PORT, SENSE_PIN) == GPIO_PIN_SET) {
            HAL_GPIO_WritePin(STATUS_PORT, STATUS_PIN, GPIO_PIN_SET);
            HAL_UART_Transmit(&huart2, on_msg, (uint16_t)(sizeof(on_msg) - 1U), 50U);
        } else {
            HAL_GPIO_WritePin(STATUS_PORT, STATUS_PIN, GPIO_PIN_RESET);
            HAL_UART_Transmit(&huart2, off_msg, (uint16_t)(sizeof(off_msg) - 1U), 50U);
        }
        HAL_Delay(1000U);
    }
}
