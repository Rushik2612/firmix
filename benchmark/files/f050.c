#include "stm32f4xx_hal.h"

#define LIMIT_PORT      GPIOB
#define LIMIT_PIN       GPIO_PIN_4
#define MOTOR_PORT      GPIOC
#define MOTOR_EN_PIN    GPIO_PIN_0
#define MOTOR_DIR_PIN   GPIO_PIN_1
#define HOMING_LIMIT    2000000UL

static uint8_t home_found;
static uint32_t home_failures;

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    gpio.Pin   = MOTOR_EN_PIN | MOTOR_DIR_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(MOTOR_PORT, &gpio);

    gpio.Pin  = LIMIT_PIN;
    gpio.Mode = GPIO_MODE_IT_RISING;
    gpio.Pull = GPIO_PULLDOWN;
    HAL_GPIO_Init(LIMIT_PORT, &gpio);

    HAL_NVIC_SetPriority(EXTI4_IRQn, 8, 0);
    HAL_NVIC_EnableIRQ(EXTI4_IRQn);
}

void EXTI4_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(LIMIT_PIN);
}

void HAL_GPIO_EXTI_Callback(uint16_t pin)
{
    if (pin == LIMIT_PIN) {
        home_found = 1U;
    }
}

static void motor_run(GPIO_PinState direction)
{
    HAL_GPIO_WritePin(MOTOR_PORT, MOTOR_DIR_PIN, direction);
    HAL_GPIO_WritePin(MOTOR_PORT, MOTOR_EN_PIN, GPIO_PIN_SET);
}

static void motor_stop(void)
{
    HAL_GPIO_WritePin(MOTOR_PORT, MOTOR_EN_PIN, GPIO_PIN_RESET);
}

static uint8_t find_home(void)
{
    uint32_t spins = 0U;

    home_found = 0U;
    motor_run(GPIO_PIN_RESET);

    while ((home_found == 0U) && (spins < HOMING_LIMIT)) {
        spins++;
    }

    motor_stop();

    if (home_found == 0U) {
        home_failures++;
        return 0U;
    }
    return 1U;
}

int main(void)
{
    HAL_Init();
    gpio_init();

    for (;;) {
        if (find_home() == 0U) {
            HAL_Delay(5000U);
            continue;
        }
        HAL_Delay(2000U);
        motor_run(GPIO_PIN_SET);
        HAL_Delay(1500U);
        motor_stop();
    }
}
