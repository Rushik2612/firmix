#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define BTN_PORT        GPIOC
#define BTN_PIN         GPIO_PIN_13
#define SETTLE_MS       15U

static SemaphoreHandle_t press_sem;

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

    gpio.Pin  = BTN_PIN;
    gpio.Mode = GPIO_MODE_IT_FALLING;
    gpio.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(BTN_PORT, &gpio);

    HAL_NVIC_SetPriority(EXTI15_10_IRQn, 8, 0);
    HAL_NVIC_EnableIRQ(EXTI15_10_IRQn);
}

void EXTI15_10_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(BTN_PIN);
}

void HAL_GPIO_EXTI_Callback(uint16_t pin)
{
    BaseType_t woken = pdFALSE;

    if (pin == BTN_PIN) {
        vTaskDelay(pdMS_TO_TICKS(SETTLE_MS));
        if (HAL_GPIO_ReadPin(BTN_PORT, BTN_PIN) == GPIO_PIN_RESET) {
            xSemaphoreGiveFromISR(press_sem, &woken);
        }
    }
    portYIELD_FROM_ISR(woken);
}

static void led_task(void *arg)
{
    (void)arg;

    for (;;) {
        if (xSemaphoreTake(press_sem, portMAX_DELAY) == pdTRUE) {
            HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        }
    }
}

int main(void)
{
    HAL_Init();

    press_sem = xSemaphoreCreateBinary();
    gpio_init();

    xTaskCreate(led_task, "led", 128, NULL, 2, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
