#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define RELAY_PORT      GPIOB
#define RELAY_PIN       GPIO_PIN_6
#define FAULT_PORT      GPIOB
#define FAULT_PIN       GPIO_PIN_2

TIM_HandleTypeDef htim4;

static SemaphoreHandle_t tick_sem;
static volatile uint8_t fault_latched;

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

    gpio.Pin = RELAY_PIN;
    HAL_GPIO_Init(RELAY_PORT, &gpio);
    HAL_GPIO_WritePin(RELAY_PORT, RELAY_PIN, GPIO_PIN_SET);

    gpio.Pin  = FAULT_PIN;
    gpio.Mode = GPIO_MODE_IT_FALLING;
    gpio.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(FAULT_PORT, &gpio);

    HAL_NVIC_SetPriority(EXTI2_IRQn, 1, 0);
    HAL_NVIC_EnableIRQ(EXTI2_IRQn);
}

static void timer4_init(void)
{
    __HAL_RCC_TIM4_CLK_ENABLE();

    htim4.Instance               = TIM4;
    htim4.Init.Prescaler         = 15999U;
    htim4.Init.CounterMode       = TIM_COUNTERMODE_UP;
    htim4.Init.Period            = 99U;
    htim4.Init.ClockDivision     = TIM_CLOCKDIVISION_DIV1;
    htim4.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
    HAL_TIM_Base_Init(&htim4);

    HAL_NVIC_SetPriority(TIM4_IRQn, 6, 0);
    HAL_NVIC_EnableIRQ(TIM4_IRQn);
}

void EXTI2_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(FAULT_PIN);
}

void TIM4_IRQHandler(void)
{
    HAL_TIM_IRQHandler(&htim4);
}

void HAL_GPIO_EXTI_Callback(uint16_t pin)
{
    if (pin == FAULT_PIN) {
        HAL_GPIO_WritePin(RELAY_PORT, RELAY_PIN, GPIO_PIN_RESET);
        fault_latched = 1U;
    }
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
    BaseType_t woken = pdFALSE;

    if (htim->Instance == TIM4) {
        xSemaphoreGiveFromISR(tick_sem, &woken);
    }
    portYIELD_FROM_ISR(woken);
}

static void supervisor_task(void *arg)
{
    (void)arg;

    for (;;) {
        if (xSemaphoreTake(tick_sem, portMAX_DELAY) == pdTRUE) {
            if (fault_latched != 0U) {
                HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);
            } else {
                HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
            }
        }
    }
}

int main(void)
{
    HAL_Init();

    tick_sem = xSemaphoreCreateBinary();
    gpio_init();
    timer4_init();

    xTaskCreate(supervisor_task, "super", 128, NULL, 2, NULL);
    HAL_TIM_Base_Start_IT(&htim4);
    vTaskStartScheduler();

    for (;;) {
    }
}
