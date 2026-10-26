#include "stm32f4xx_hal.h"

#define DATA_PORT       GPIOB
#define DATA_PIN        GPIO_PIN_3
#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define BIT_COUNT       8U

static void data_pin_output(void)
{
    GPIO_InitTypeDef gpio = {0};

    gpio.Pin   = DATA_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_OD;
    gpio.Pull  = GPIO_PULLUP;
    gpio.Speed = GPIO_SPEED_FREQ_MEDIUM;
    HAL_GPIO_Init(DATA_PORT, &gpio);
}

static void data_pin_input(void)
{
    GPIO_InitTypeDef gpio = {0};

    gpio.Pin  = DATA_PIN;
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(DATA_PORT, &gpio);
}

static void led_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    gpio.Pin   = LED_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &gpio);
}

static void delay_us(uint32_t us)
{
    volatile uint32_t n = us * 4U;

    while (n-- > 0U) {
    }
}

static uint8_t read_frame(void)
{
    uint8_t value = 0U;
    uint32_t i;

    data_pin_output();
    HAL_GPIO_WritePin(DATA_PORT, DATA_PIN, GPIO_PIN_RESET);
    HAL_Delay(18U);
    HAL_GPIO_WritePin(DATA_PORT, DATA_PIN, GPIO_PIN_SET);
    delay_us(30U);

    data_pin_input();
    for (i = 0U; i < BIT_COUNT; i++) {
        delay_us(50U);
        value = (uint8_t)((value << 1) | (HAL_GPIO_ReadPin(DATA_PORT, DATA_PIN) == GPIO_PIN_SET));
    }

    return value;
}

int main(void)
{
    HAL_Init();
    led_init();

    for (;;) {
        uint8_t frame = read_frame();

        HAL_GPIO_WritePin(LED_PORT, LED_PIN, (frame > 0x80U) ? GPIO_PIN_SET : GPIO_PIN_RESET);
        HAL_Delay(2000U);
    }
}
