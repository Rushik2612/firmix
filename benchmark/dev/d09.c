#include "stm32f4xx_hal.h"

#define STATUS_PORT     GPIOB
#define STATUS_PIN      GPIO_PIN_0
#define ALARM_PORT      GPIOB
#define ALARM_PIN       GPIO_PIN_1
#define DOOR_PORT       GPIOB
#define DOOR_PIN        GPIO_PIN_2

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOB_CLK_ENABLE();

    gpio.Pin   = STATUS_PIN | ALARM_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOB, &gpio);

    gpio.Pin  = DOOR_PIN;
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(DOOR_PORT, &gpio);
}

int main(void)
{
    HAL_Init();
    gpio_init();

    for (;;) {
        if (HAL_GPIO_ReadPin(DOOR_PORT, DOOR_PIN) == GPIO_PIN_SET) {
            HAL_GPIO_WritePin(DOOR_PORT, DOOR_PIN, GPIO_PIN_SET);
            HAL_GPIO_WritePin(STATUS_PORT, STATUS_PIN, GPIO_PIN_SET);
        } else {
            HAL_GPIO_WritePin(ALARM_PORT, ALARM_PIN, GPIO_PIN_RESET);
            HAL_GPIO_WritePin(STATUS_PORT, STATUS_PIN, GPIO_PIN_RESET);
        }
        HAL_Delay(20U);
    }
}
