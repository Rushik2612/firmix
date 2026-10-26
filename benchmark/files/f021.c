#include "stm32f4xx_hal.h"
#include <string.h>

#define PAYLOAD_MAX     32U
#define LINE_MAX_LEN    48U
#define NAME_LEN        16U
#define LED_PORT        GPIOB
#define LED_PIN         GPIO_PIN_0

UART_HandleTypeDef huart1;

static uint8_t payload[PAYLOAD_MAX];
static char rx_line[LINE_MAX_LEN];
static char device_name[NAME_LEN] = "unnamed";

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
    if (len > PAYLOAD_MAX) {
        len = PAYLOAD_MAX;
    }

    for (i = 0U; i < len; i++) {
        if (HAL_UART_Receive(&huart1, &byte, 1U, 50U) != HAL_OK) {
            return -2;
        }
        payload[i] = byte;
    }

    return (int)len;
}

static int read_line(void)
{
    uint8_t c;
    size_t n = 0U;

    for (;;) {
        if (HAL_UART_Receive(&huart1, &c, 1U, 500U) != HAL_OK) {
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

static void apply_name(void)
{
    if (strncmp(rx_line, "name=", 5U) == 0) {
        strncpy(device_name, &rx_line[5], NAME_LEN - 1U);
        device_name[NAME_LEN - 1U] = '\0';
        HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
    }
}

int main(void)
{
    HAL_Init();
    uart1_init();

    for (;;) {
        if (receive_message() > 0) {
            payload[0] ^= 0x01U;
        }
        if (read_line() > 0) {
            apply_name();
        }
    }
}
