#include "stm32f4xx_hal.h"

#define LED_PORT        GPIOB
#define LED_PIN         GPIO_PIN_0
#define BEAT_PORT       GPIOA
#define BEAT_PIN        GPIO_PIN_6

TIM_HandleTypeDef htim2;

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

    gpio.Pin = BEAT_PIN;
    HAL_GPIO_Init(BEAT_PORT, &gpio);
}

static void timer2_init(void)
{
    htim2.Instance               = TIM2;
    htim2.Init.Prescaler         = 15999U;
    htim2.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim2.Init.Period            = 249U;
    htim2.Init.ClockDivision     = TIM_CLOCKDIVISION_DIV1;
    htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    HAL_TIM_Base_Init(&htim2);

    HAL_NVIC_SetPriority(TIM2_IRQn, 6, 0);
    HAL_NVIC_EnableIRQ(TIM2_IRQn);
    HAL_TIM_Base_Start_IT(&htim2);
}

void TIM2_IRQHandler(void)
{
    HAL_TIM_IRQHandler(&htim2);
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
    if (htim->Instance == TIM2) {
        HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
    }
}

int main(void)
{
    HAL_Init();
    gpio_init();
    timer2_init();

    for (;;) {
        HAL_GPIO_TogglePin(BEAT_PORT, BEAT_PIN);
        HAL_Delay(1000U);
    }
}
