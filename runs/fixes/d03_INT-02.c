#include "stm32f4xx_hal.h"

#define RX_BUF_LEN      32U
#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5

UART_HandleTypeDef huart2;

static uint8_t rx_byte;
static volatile uint8_t rx_buf[RX_BUF_LEN];
static volatile uint8_t rx_count;
static uint8_t rx_head;
static uint8_t rx_tail;

static void uart2_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_USART2_CLK_ENABLE();

    gpio.Pin       = GPIO_PIN_2 | GPIO_PIN_3;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_PULLUP;
    gpio.Speed     = GPIO_SPEED_FREQ_VERY_HIGH;
    gpio.Alternate = GPIO_AF7_USART2;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin       = LED_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_LOW;
    gpio.Alternate = 0U;
    HAL_GPIO_Init(LED_PORT, &gpio);

    huart2.Instance          = USART2;
    huart2.Init.BaudRate     = 115200U;
    huart2.Init.WordLength   = UART_WORDLENGTH_8B;
    huart2.Init.StopBits     = UART_STOPBITS_1;
    huart2.Init.Parity       = UART_PARITY_NONE;
    huart2.Init.Mode         = UART_MODE_TX_RX;
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

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART2) {
        if (rx_count < RX_BUF_LEN) {
            rx_buf[rx_head] = rx_byte;
            rx_head = (uint8_t)((rx_head + 1U) % RX_BUF_LEN);
            rx_count++;
        }
        HAL_UART_Receive_IT(&huart2, &rx_byte, 1U);
    }
}

static void handle_byte(uint8_t b)
{
    if (b == '1') {
        HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);
    } else if (b == '0') {
        HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_RESET);
    }
}

int main(void)
{
    HAL_Init();
    uart2_init();
    HAL_UART_Receive_IT(&huart2, &rx_byte, 1U);

     xPortEnterCritical();

        if (rx_count > 0U) {
            uint8_t b = rx_buf[rx_tail];
            rx_tail = (uint8_t)((rx_tail + 1U) % RX_BUF_LEN);
            rx_count--;
            handle_byte(b);
        }
     xPortExitCritical();

}
