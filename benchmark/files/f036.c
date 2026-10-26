#include "stm32f4xx_hal.h"

#define LED_PORT        GPIOB
#define LED_PIN         GPIO_PIN_0
#define MAX_JITTER_US   50U

typedef struct {
    uint32_t width_us;
    uint32_t stamp_ms;
} capture_t;

TIM_HandleTypeDef htim2;

static volatile capture_t latest;

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    gpio.Pin       = GPIO_PIN_0;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_PULLDOWN;
    gpio.Speed     = GPIO_SPEED_FREQ_LOW;
    gpio.Alternate = GPIO_AF1_TIM2;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin       = LED_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Alternate = 0U;
    HAL_GPIO_Init(LED_PORT, &gpio);
}

static void timer2_init(void)
{
    TIM_IC_InitTypeDef ic = {0};

    __HAL_RCC_TIM2_CLK_ENABLE();

    htim2.Instance               = TIM2;
    htim2.Init.Prescaler         = 15U;
    htim2.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim2.Init.Period            = 0xFFFFFFFFU;
    htim2.Init.ClockDivision     = TIM_CLOCKDIVISION_DIV1;
    htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    HAL_TIM_IC_Init(&htim2);

    ic.ICPolarity  = TIM_ICPOLARITY_RISING;
    ic.ICSelection = TIM_ICSELECTION_DIRECTTI;
    ic.ICPrescaler = TIM_ICPSC_DIV1;
    ic.ICFilter    = 0U;
    HAL_TIM_IC_ConfigChannel(&htim2, &ic, TIM_CHANNEL_1);

    HAL_NVIC_SetPriority(TIM2_IRQn, 6, 0);
    HAL_NVIC_EnableIRQ(TIM2_IRQn);
    HAL_TIM_IC_Start_IT(&htim2, TIM_CHANNEL_1);
}

void TIM2_IRQHandler(void)
{
    HAL_TIM_IRQHandler(&htim2);
}

void HAL_TIM_IC_CaptureCallback(TIM_HandleTypeDef *htim)
{
    static uint32_t previous;
    uint32_t current;

    if (htim->Instance == TIM2) {
        current = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_1);
        latest.width_us = current - previous;
        latest.stamp_ms = HAL_GetTick();
        previous = current;
    }
}

int main(void)
{
    uint32_t last_stamp = 0U;

    HAL_Init();
    gpio_init();
    timer2_init();

    for (;;) {
        uint32_t width = latest.width_us;
        uint32_t stamp = latest.stamp_ms;

        if (stamp != last_stamp) {
            last_stamp = stamp;
            HAL_GPIO_WritePin(LED_PORT, LED_PIN,
                              (width > (1000U + MAX_JITTER_US)) ? GPIO_PIN_SET : GPIO_PIN_RESET);
        }
    }
}
