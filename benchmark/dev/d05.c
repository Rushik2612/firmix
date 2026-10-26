#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define BUTTON_PIN      GPIO_PIN_13

static SemaphoreHandle_t button_sem;

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
        xSemaphoreGive(button_sem);
    }
}

static void led_task(void *arg)
{
    (void)arg;

    for (;;) {
        if (xSemaphoreTake(button_sem, portMAX_DELAY) == pdTRUE) {
            HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        }
    }
}

int main(void)
{
    HAL_Init();

    button_sem = xSemaphoreCreateBinary();
    gpio_init();

    xTaskCreate(led_task, "led", 128, NULL, 2, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
