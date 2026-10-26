#include "stm32f4xx_hal.h"

#define LED_PORT        GPIOB
#define LED_PIN         GPIO_PIN_0
#define BTN_A_PIN       GPIO_PIN_0
#define BTN_B_PIN       GPIO_PIN_1

static volatile uint32_t press_events;
static uint32_t last_seen;

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    gpio.Pin   = LED_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &gpio);

    gpio.Pin  = BTN_A_PIN | BTN_B_PIN;
    gpio.Mode = GPIO_MODE_IT_FALLING;
    gpio.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOA, &gpio);

    HAL_NVIC_SetPriority(EXTI0_IRQn, 6, 0);
    HAL_NVIC_SetPriority(EXTI1_IRQn, 6, 0);
    HAL_NVIC_EnableIRQ(EXTI0_IRQn);
    HAL_NVIC_EnableIRQ(EXTI1_IRQn);
}

void EXTI0_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(BTN_A_PIN);
}

void EXTI1_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(BTN_B_PIN);
}

void HAL_GPIO_EXTI_Callback(uint16_t pin)
{
    if ((pin == BTN_A_PIN) || (pin == BTN_B_PIN)) {
        press_events++;
    }
}

int main(void)
{
    HAL_Init();
    gpio_init();

    for (;;) {
        uint32_t now = press_events;

        if (now != last_seen) {
            last_seen = now;
            HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        }
    }
}
