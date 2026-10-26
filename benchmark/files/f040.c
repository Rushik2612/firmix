#include "stm32f4xx_hal.h"
#include <string.h>

#define LINE_MAX_LEN    64U
#define NAME_LEN        16U
#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5

UART_HandleTypeDef huart6;

static char rx_line[LINE_MAX_LEN];
static char device_name[NAME_LEN] = "unnamed";

static void uart6_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
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
    huart6.Init.BaudRate     = 9600U;
    huart6.Init.WordLength   = UART_WORDLENGTH_8B;
    huart6.Init.StopBits     = UART_STOPBITS_1;
    huart6.Init.Parity       = UART_PARITY_NONE;
    huart6.Init.Mode         = UART_MODE_TX_RX;
    huart6.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart6.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart6);
}

static int read_line(void)
{
    uint8_t c;
    size_t n = 0U;

    for (;;) {
        if (HAL_UART_Receive(&huart6, &c, 1U, 500U) != HAL_OK) {
            return -1;
        }
        if (c == '\n') {
            break;
        }
        if (n < (LINE_MAX_LEN - 1U)) {
            rx_line[n++] = (char)c;
        }
    }

    rx_line[n] = '\0';
    return (int)n;
}

static void apply_command(void)
{
    if (strncmp(rx_line, "name=", 5U) == 0) {
        strcpy(device_name, &rx_line[5]);
        HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
    }
}

int main(void)
{
    HAL_Init();
    uart6_init();

    for (;;) {
        if (read_line() > 0) {
            apply_command();
        }
    }
}
