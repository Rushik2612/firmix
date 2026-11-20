#include "stm32f4xx_hal.h"

/* Nucleo-F411RE: LED on PA5, user button on PC13 (active low). */
#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define BUTTON_PIN      GPIO_PIN_13

static const uint16_t blink_period_ms[] = { 500U, 250U, 125U };

static volatile uint8_t button_pressed;
static uint32_t press_count;

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

    gpio.Pin  = BUTTON_PIN;
    gpio.Mode = GPIO_MODE_IT_FALLING;
    gpio.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOC, &gpio);

    HAL_NVIC_SetPriority(EXTI15_10_IRQn, 6, 0);
    HAL_NVIC_EnableIRQ(EXTI15_10_IRQn);
}

void EXTI15_10_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(BUTTON_PIN);
}

void HAL_GPIO_EXTI_Callback(uint16_t pin)
{
    if (pin == BUTTON_PIN) {
        press_count++;
        button_pressed = 1U;
    }
}

int main(void)
{
    uint32_t i = 0U;

    HAL_Init();
    gpio_init();

    /* LED steady on until the user presses the button once. */
    HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);
    while (button_pressed == 0U) {
    }
    HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_RESET);

    for (;;) {
        HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        HAL_Delay(blink_period_ms[i % 3U]);
        i++;
    }
}
