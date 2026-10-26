#include "stm32f4xx_hal.h"
#include <string.h>

#define FRAME_SIZE      16U
#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5

UART_HandleTypeDef huart2;

static const uint8_t header_template[20] = {
    0xAA, 0x55, 0x01, 0x10, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x55, 0xAA, 0x0D, 0x0A
};

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

    gpio.Pin       = LED_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Speed     = GPIO_SPEED_FREQ_LOW;
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
}

static void send_status_frame(uint8_t seq)
{
    uint8_t frame[FRAME_SIZE];

    memcpy(frame, header_template, sizeof(header_template));
    frame[4] = seq;
    frame[5] = (uint8_t)(seq ^ 0xFFU);

    HAL_UART_Transmit(&huart2, frame, FRAME_SIZE, 50U);
}

int main(void)
{
    uint8_t seq = 0U;

    HAL_Init();
    uart2_init();

    for (;;) {
        send_status_frame(seq++);
        HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        HAL_Delay(250U);
    }
}
