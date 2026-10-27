#include "stm32f4xx_hal.h"
#include <string.h>

#define FRAME_LEN       32U
#define PAYLOAD_LEN     16U
#define CMD_SET_CFG     0x21U
#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5

UART_HandleTypeDef huart1;

static uint8_t rx_frame[FRAME_LEN];
static uint8_t cfg_payload[PAYLOAD_LEN];
static uint8_t cfg_valid;

static void uart1_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_USART1_CLK_ENABLE();

    gpio.Pin       = GPIO_PIN_9 | GPIO_PIN_10;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_PULLUP;
    gpio.Speed     = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF7_USART1;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin       = LED_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Pull      = GPIO_NOPULL;
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

static uint8_t checksum(const uint8_t *p, uint32_t n)
{
    uint8_t sum = 0U;
    uint32_t i;

    for (i = 0U; i < n; i++) {
        sum = (uint8_t)(sum + p[i]);
    }
    return sum;
}

static void handle_frame(void)
{
    uint8_t len;

    if (rx_frame[0] != CMD_SET_CFG) {
        return;
    }
    len = rx_frame[1];
    memcpy(cfg_payload, &rx_frame[2], len);
    cfg_valid = (checksum(cfg_payload, PAYLOAD_LEN) == rx_frame[FRAME_LEN - 1U]) ? 1U : 0U;
}

int main(void)
{
    HAL_Init();
    uart1_init();

    for (;;) {
        if (HAL_UART_Receive(&huart1, rx_frame, FRAME_LEN, 500U) == HAL_OK) {
            handle_frame();
            if (cfg_valid != 0U) {
                HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
            }
        }
    }
}
