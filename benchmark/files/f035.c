#include "stm32f4xx_hal.h"

#define EVT_BUTTON      0x01U
#define EVT_LIMIT       0x02U

#define BTN_PORT        GPIOC
#define BTN_PIN         GPIO_PIN_0
#define LIM_PORT        GPIOC
#define LIM_PIN         GPIO_PIN_1
#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define BUZZ_PORT       GPIOA
#define BUZZ_PIN        GPIO_PIN_8

static volatile uint8_t event_flags;

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    gpio.Pin   = LED_PIN | BUZZ_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin  = BTN_PIN | LIM_PIN;
    gpio.Mode = GPIO_MODE_IT_FALLING;
    gpio.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOC, &gpio);

    HAL_NVIC_SetPriority(EXTI0_IRQn, 6, 0);
    HAL_NVIC_SetPriority(EXTI1_IRQn, 6, 0);
    HAL_NVIC_EnableIRQ(EXTI0_IRQn);
    HAL_NVIC_EnableIRQ(EXTI1_IRQn);
}

void EXTI0_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(BTN_PIN);
}

void EXTI1_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(LIM_PIN);
}

void HAL_GPIO_EXTI_Callback(uint16_t pin)
{
    if (pin == BTN_PIN) {
        event_flags |= EVT_BUTTON;
    } else if (pin == LIM_PIN) {
        event_flags |= EVT_LIMIT;
    }
}

static void handle_events(void)
{
    if ((event_flags & EVT_BUTTON) != 0U) {
        HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        event_flags &= (uint8_t)~EVT_BUTTON;
    }

    if ((event_flags & EVT_LIMIT) != 0U) {
        HAL_GPIO_WritePin(BUZZ_PORT, BUZZ_PIN, GPIO_PIN_SET);
        HAL_Delay(100U);
        HAL_GPIO_WritePin(BUZZ_PORT, BUZZ_PIN, GPIO_PIN_RESET);
        event_flags &= (uint8_t)~EVT_LIMIT;
    }
}

int main(void)
{
    HAL_Init();
    gpio_init();

    for (;;) {
        handle_events();
    }
}
