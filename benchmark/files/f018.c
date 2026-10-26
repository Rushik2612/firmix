#include "stm32f4xx_hal.h"

#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define BLINK_PERIOD_US 500000ULL

TIM_HandleTypeDef htim4;

static volatile uint64_t uptime_us;

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();

    gpio.Pin   = LED_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &gpio);
}

static void timer4_init(void)
{
    __HAL_RCC_TIM4_CLK_ENABLE();

    htim4.Instance               = TIM4;
    htim4.Init.Prescaler         = 15U;
    htim4.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim4.Init.Period            = 999U;
    htim4.Init.ClockDivision     = TIM_CLOCKDIVISION_DIV1;
    htim4.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    HAL_TIM_Base_Init(&htim4);

    HAL_NVIC_SetPriority(TIM4_IRQn, 4, 0);
    HAL_NVIC_EnableIRQ(TIM4_IRQn);
    HAL_TIM_Base_Start_IT(&htim4);
}

void TIM4_IRQHandler(void)
{
    HAL_TIM_IRQHandler(&htim4);
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
    if (htim->Instance == TIM4) {
        uptime_us += 1000U;
    }
}

static uint64_t uptime_now(void)
{
    uint64_t now = uptime_us;

    return now;
}

int main(void)
{
    uint64_t last_toggle = 0U;

    HAL_Init();
    gpio_init();
    timer4_init();

    for (;;) {
        uint64_t now = uptime_now();

        if ((now - last_toggle) >= BLINK_PERIOD_US) {
            HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
            last_toggle = now;
        }
    }
}
