#include "stm32f4xx_hal.h"

#define BTN_PORT        GPIOC
#define BTN_PIN         GPIO_PIN_13
#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define DEBOUNCE_MS     20U
#define LONG_PRESS_MS   800U

static volatile uint32_t last_press_tick;

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    gpio.Pin   = LED_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &gpio);

    gpio.Pin  = BTN_PIN;
    gpio.Mode = GPIO_MODE_IT_FALLING;
    gpio.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(BTN_PORT, &gpio);

    HAL_NVIC_SetPriority(EXTI15_10_IRQn, 6, 0);
    HAL_NVIC_EnableIRQ(EXTI15_10_IRQn);
}

void EXTI15_10_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(BTN_PIN);
}

void HAL_GPIO_EXTI_Callback(uint16_t pin)
{
    if (pin == BTN_PIN) {
        HAL_Delay(DEBOUNCE_MS);
        if (HAL_GPIO_ReadPin(BTN_PORT, BTN_PIN) == GPIO_PIN_RESET) {
            last_press_tick = HAL_GetTick();
        }
    }
}

int main(void)
{
    uint32_t seen = 0U;

    HAL_Init();
    gpio_init();

    for (;;) {
        uint32_t t = last_press_tick;

        if (t != seen) {
            seen = t;
            HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);
            HAL_Delay(LONG_PRESS_MS);
            HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_RESET);
        }
    }
}
