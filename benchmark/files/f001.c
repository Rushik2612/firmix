#include "stm32f4xx_hal.h"

#define RX_BUF_SIZE     64U
#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5

UART_HandleTypeDef huart1;

static volatile uint8_t rx_buf[RX_BUF_SIZE];
static volatile uint32_t rx_count;
static uint32_t rx_head;
static uint32_t rx_tail;
static uint8_t rx_byte;

static void uart1_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
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
    huart1.Init.BaudRate     = 57600U;
    huart1.Init.WordLength   = UART_WORDLENGTH_8B;
    huart1.Init.StopBits     = UART_STOPBITS_1;
    huart1.Init.Parity       = UART_PARITY_NONE;
    huart1.Init.Mode         = UART_MODE_RX;
    huart1.Init.HwFlowCtl    = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    HAL_UART_Init(&huart1);

    HAL_NVIC_SetPriority(USART1_IRQn, 6, 0);
    HAL_NVIC_EnableIRQ(USART1_IRQn);
}

void USART1_IRQHandler(void)
{
    HAL_UART_IRQHandler(&huart1);
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1) {
        if (rx_count < RX_BUF_SIZE) {
            rx_buf[rx_head] = rx_byte;
            rx_head = (rx_head + 1U) % RX_BUF_SIZE;
            rx_count++;
        }
        HAL_UART_Receive_IT(&huart1, &rx_byte, 1U);
    }
}

static int rx_pop(uint8_t *out)
{
    int have = 0;

    __disable_irq();
    if (rx_count > 0U) {
        *out = rx_buf[rx_tail];
        rx_tail = (rx_tail + 1U) % RX_BUF_SIZE;
        rx_count--;
        have = 1;
    }
    __enable_irq();

    return have;
}

int main(void)
{
    uint8_t c;

    HAL_Init();
    uart1_init();
    HAL_UART_Receive_IT(&huart1, &rx_byte, 1U);

    for (;;) {
        if (rx_pop(&c) != 0) {
            if (c == '!') {
                HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
            }
        }
    }
}
