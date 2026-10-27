#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"

#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define BTN_PIN         GPIO_PIN_0
#define EVT_QUEUE_LEN   8U

static QueueHandle_t evt_queue;

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();

    gpio.Pin   = LED_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &gpio);

    gpio.Pin  = BTN_PIN;
    gpio.Mode = GPIO_MODE_IT_RISING;
    gpio.Pull = GPIO_PULLDOWN;
    HAL_GPIO_Init(GPIOA, &gpio);

    HAL_NVIC_SetPriority(EXTI0_IRQn, 5, 0);
    HAL_NVIC_EnableIRQ(EXTI0_IRQn);
}

void EXTI0_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(BTN_PIN);
}

void HAL_GPIO_EXTI_Callback(uint16_t pin)
{
    BaseType_t woken = pdFALSE;
    uint16_t evt = pin;

    xQueueSendFromISR(evt_queue, &evt, &woken);
    portYIELD_FROM_ISR(woken);
}

static void led_task(void *arg)
{
    uint16_t evt;
    (void)arg;

    for (;;) {
        if (xQueueReceive(evt_queue, &evt, portMAX_DELAY) == pdTRUE) {
            HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        }
    }
}

int main(void)
{
    HAL_Init();
    gpio_init();

    evt_queue = xQueueCreate(EVT_QUEUE_LEN, sizeof(uint16_t));
    xTaskCreate(led_task, "led", 128, NULL, 2, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
