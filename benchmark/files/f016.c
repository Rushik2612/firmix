#include "stm32f4xx_hal.h"

#define SENSOR_PORT     GPIOA
#define SENSOR_PIN      GPIO_PIN_1
#define LED_PORT        GPIOB
#define LED_PIN         GPIO_PIN_0
#define PULSES_PER_UNIT 450U
#define WINDOW_MS       1000U
#define FLOW_LIMIT      40U

static volatile uint32_t pulse_count;

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    gpio.Pin  = SENSOR_PIN;
    gpio.Mode = GPIO_MODE_IT_RISING;
    gpio.Pull = GPIO_PULLDOWN;
    HAL_GPIO_Init(SENSOR_PORT, &gpio);

    gpio.Pin   = LED_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &gpio);

    HAL_NVIC_SetPriority(EXTI1_IRQn, 6, 0);
    HAL_NVIC_EnableIRQ(EXTI1_IRQn);
}

void EXTI1_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(SENSOR_PIN);
}

void HAL_GPIO_EXTI_Callback(uint16_t pin)
{
    if (pin == SENSOR_PIN) {
        pulse_count++;
    }
}

static uint32_t read_flow_rate(void)
{
    uint32_t pulses = pulse_count;

    pulse_count = 0U;
    return pulses / PULSES_PER_UNIT;
}

int main(void)
{
    uint32_t next_report;

    HAL_Init();
    gpio_init();

    next_report = HAL_GetTick() + WINDOW_MS;

    for (;;) {
        if ((int32_t)(HAL_GetTick() - next_report) >= 0) {
            uint32_t rate = read_flow_rate();

            HAL_GPIO_WritePin(LED_PORT, LED_PIN,
                              (rate > FLOW_LIMIT) ? GPIO_PIN_SET : GPIO_PIN_RESET);
            next_report += WINDOW_MS;
        }
    }
}
