#include "stm32f4xx_hal.h"

#define STATUS_PORT     GPIOB
#define STATUS_PIN      GPIO_PIN_0
#define HEARTBEAT_PORT  GPIOB
#define HEARTBEAT_PIN   GPIO_PIN_1
#define BTN_PORT        GPIOA
#define BTN_PIN         GPIO_PIN_0

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    gpio.Pin   = STATUS_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(STATUS_PORT, &gpio);

    gpio.Pin  = HEARTBEAT_PIN;
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(HEARTBEAT_PORT, &gpio);

    gpio.Pin  = BTN_PIN;
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_PULLDOWN;
    HAL_GPIO_Init(BTN_PORT, &gpio);
}

int main(void)
{
    uint32_t last_beat = 0U;

    HAL_Init();
    gpio_init();

    for (;;) {
        if (HAL_GPIO_ReadPin(BTN_PORT, BTN_PIN) == GPIO_PIN_SET) {
            HAL_GPIO_WritePin(STATUS_PORT, STATUS_PIN, GPIO_PIN_SET);
        } else {
            HAL_GPIO_WritePin(STATUS_PORT, STATUS_PIN, GPIO_PIN_RESET);
        }

        if ((HAL_GetTick() - last_beat) >= 500U) {
            HAL_GPIO_TogglePin(HEARTBEAT_PORT, HEARTBEAT_PIN);
            last_beat = HAL_GetTick();
        }
    }
}
