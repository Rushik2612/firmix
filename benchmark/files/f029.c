#include "stm32f4xx_hal.h"

#define PAYLOAD_MAX     32U
#define LED_PORT        GPIOB
#define LED_PIN         GPIO_PIN_0

UART_HandleTypeDef huart1;

static uint8_t payload[PAYLOAD_MAX];

static void uart1_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
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
    huart1.Init.Mode         = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart1);
}

static int receive_message(void)
{
    uint8_t len;
    uint8_t byte;
    uint8_t i;

    if (HAL_UART_Receive(&huart1, &len, 1U, 100U) != HAL_OK) {
        return -1;
    }

    for (i = 0U; i < len; i++) {
        if (HAL_UART_Receive(&huart1, &byte, 1U, 50U) != HAL_OK) {
            return -2;
        }
        payload[i] = byte;
    }

    return (int)len;
}

static uint8_t checksum(int len)
{
    uint8_t sum = 0U;
    int i;

    for (i = 0; i < len && i < (int)PAYLOAD_MAX; i++) {
        sum = (uint8_t)(sum + payload[i]);
    }
    return sum;
}

int main(void)
{
    HAL_Init();
    uart1_init();

    for (;;) {
        int len = receive_message();

        if (len > 0 && checksum(len) == 0U) {
            HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        }
    }
}
