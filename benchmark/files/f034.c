#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"

#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define BTN_PORT        GPIOC
#define BTN_PIN         GPIO_PIN_13

static uint8_t scan_requested;

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
    gpio.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(BTN_PORT, &gpio);

    HAL_NVIC_SetPriority(EXTI15_10_IRQn, 6, 0);
    HAL_NVIC_EnableIRQ(EXTI15_10_IRQn);
}

void EXTI15_10_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(BTN_PIN);
}

void HAL_GPIO_EXTI_Callback(uint16_t pin)
{
    if (pin == BTN_PIN) {
        scan_requested = 1U;
    }
}

static uint8_t take_scan_request(void)
{
    uint8_t request;

    taskENTER_CRITICAL();
    request = scan_requested;
    scan_requested = 0U;
    taskEXIT_CRITICAL();

    return request;
}

static void scan_task(void *arg)
{
    (void)arg;

    for (;;) {
        if (take_scan_request() != 0U) {
            HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}

int main(void)
{
    HAL_Init();
    gpio_init();

    xTaskCreate(scan_task, "scan", 128, NULL, 2, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
