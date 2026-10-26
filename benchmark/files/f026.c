#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"

#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define WORKER_STACK    128U

TIM_HandleTypeDef htim3;

static TaskHandle_t worker_handle;

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

static void timer3_init(void)
{
    __HAL_RCC_TIM3_CLK_ENABLE();

    htim3.Instance               = TIM3;
    htim3.Init.Prescaler         = 15999U;
    htim3.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim3.Init.Period            = 499U;
    htim3.Init.ClockDivision     = TIM_CLOCKDIVISION_DIV1;
    htim3.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    HAL_TIM_Base_Init(&htim3);

    HAL_NVIC_SetPriority(TIM3_IRQn, 4, 0);
    HAL_NVIC_EnableIRQ(TIM3_IRQn);
}

void TIM3_IRQHandler(void)
{
    HAL_TIM_IRQHandler(&htim3);
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
    BaseType_t woken = pdFALSE;

    if (htim->Instance == TIM3) {
        vTaskNotifyGiveFromISR(worker_handle, &woken);
    }
    portYIELD_FROM_ISR(woken);
}

static void worker_task(void *arg)
{
    (void)arg;

    for (;;) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
    }
}

int main(void)
{
    HAL_Init();
    gpio_init();

    xTaskCreate(worker_task, "worker", WORKER_STACK, NULL, 3, &worker_handle);

    timer3_init();
    HAL_TIM_Base_Start_IT(&htim3);

    vTaskStartScheduler();

    for (;;) {
    }
}
