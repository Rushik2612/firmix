#include "stm32f4xx_hal.h"

#define LED_PORT        GPIOB
#define LED_PIN         GPIO_PIN_1

UART_HandleTypeDef huart6;

static uint8_t rx_byte;
static volatile uint32_t echoed;

static void uart6_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_USART6_CLK_ENABLE();

    gpio.Pin       = GPIO_PIN_11 | GPIO_PIN_12;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_PULLUP;
    gpio.Speed     = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF8_USART6;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin       = LED_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_LOW;
    gpio.Alternate = 0U;
    HAL_GPIO_Init(LED_PORT, &gpio);

    huart6.Instance          = USART6;
    huart6.Init.BaudRate     = 38400U;
    huart6.Init.WordLength   = UART_WORDLENGTH_8B;
    huart6.Init.StopBits     = UART_STOPBITS_1;
    huart6.Init.Parity       = UART_PARITY_NONE;
    huart6.Init.Mode         = UART_MODE_TX_RX;
    huart6.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart6.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart6);

    HAL_NVIC_SetPriority(USART6_IRQn, 7, 0);
    HAL_NVIC_EnableIRQ(USART6_IRQn);
}

void USART6_IRQHandler(void)
{
    HAL_UART_IRQHandler(&huart6);
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART6) {
        huart->Instance->DR = (uint32_t)rx_byte;
        while (__HAL_UART_GET_FLAG(huart, UART_FLAG_TC) == RESET) {
        }
        echoed++;
        HAL_UART_Receive_IT(&huart6, &rx_byte, 1U);
    }
}

int main(void)
{
    uint32_t last = 0U;

    HAL_Init();
    uart6_init();
    HAL_UART_Receive_IT(&huart6, &rx_byte, 1U);

    for (;;) {
        uint32_t now = echoed;

        if (now != last) {
            last = now;
            HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        }
    }
}
