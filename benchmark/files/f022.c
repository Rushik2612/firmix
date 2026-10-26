#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

#define LED_PORT        GPIOB
#define LED_PIN         GPIO_PIN_0
#define KEY_PORT        GPIOA
#define KEY_PIN         GPIO_PIN_0

static SemaphoreHandle_t key_sem;

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

    gpio.Pin  = KEY_PIN;
    gpio.Mode = GPIO_MODE_IT_RISING;
    gpio.Pull = GPIO_PULLDOWN;
    HAL_GPIO_Init(KEY_PORT, &gpio);

    HAL_NVIC_SetPriority(EXTI0_IRQn, 1, 0);
    HAL_NVIC_EnableIRQ(EXTI0_IRQn);
}

void EXTI0_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(KEY_PIN);
}

void HAL_GPIO_EXTI_Callback(uint16_t pin)
{
    BaseType_t woken = pdFALSE;

    if (pin == KEY_PIN) {
        xSemaphoreGiveFromISR(key_sem, &woken);
    }
    portYIELD_FROM_ISR(woken);
}

static void key_task(void *arg)
{
    (void)arg;

    for (;;) {
        if (xSemaphoreTake(key_sem, portMAX_DELAY) == pdTRUE) {
            HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        }
    }
}

int main(void)
{
    HAL_Init();

    key_sem = xSemaphoreCreateBinary();
    gpio_init();

    xTaskCreate(key_task, "key", 128, NULL, 2, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
