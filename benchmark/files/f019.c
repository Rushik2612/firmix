#include "stm32f4xx_hal.h"
#include <stdio.h>

#define LED_PORT        GPIOB
#define LED_PIN         GPIO_PIN_0

TIM_HandleTypeDef htim5;

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOB_CLK_ENABLE();

    gpio.Pin   = LED_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &gpio);
}

static void timer5_init(void)
{
    __HAL_RCC_TIM5_CLK_ENABLE();

    htim5.Instance               = TIM5;
    htim5.Init.Prescaler         = 15999U;
    htim5.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim5.Init.Period            = 999U;
    htim5.Init.ClockDivision     = TIM_CLOCKDIVISION_DIV1;
    htim5.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    HAL_TIM_Base_Init(&htim5);

    HAL_NVIC_SetPriority(TIM5_IRQn, 9, 0);
    HAL_NVIC_EnableIRQ(TIM5_IRQn);
    HAL_TIM_Base_Start_IT(&htim5);
}

void TIM5_IRQHandler(void)
{
    HAL_TIM_IRQHandler(&htim5);
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
    static uint32_t seconds;

    if (htim->Instance == TIM5) {
        seconds++;
        printf("uptime=%lu s tick=%lu\r\n",
               (unsigned long)seconds, (unsigned long)HAL_GetTick());
    }
}

int main(void)
{
    HAL_Init();
    gpio_init();
    timer5_init();

    for (;;) {
        HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        HAL_Delay(250U);
    }
}
