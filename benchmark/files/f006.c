#include "stm32f4xx_hal.h"

#define LIGHT_PORT      GPIOA
#define LIGHT_PIN       GPIO_PIN_1
#define BACKLIGHT_PORT  GPIOA
#define BACKLIGHT_PIN   GPIO_PIN_4
#define DARK_LEVEL      900U

ADC_HandleTypeDef hadc1;

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();

    gpio.Pin  = LIGHT_PIN | BACKLIGHT_PIN;
    gpio.Mode = GPIO_MODE_ANALOG;
    gpio.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &gpio);
}

static void adc1_init(void)
{
    ADC_ChannelConfTypeDef ch = {0};

    __HAL_RCC_ADC1_CLK_ENABLE();

    hadc1.Instance                   = ADC1;
    hadc1.Init.ClockPrescaler        = ADC_CLOCK_SYNC_PCLK_DIV6;
    hadc1.Init.Resolution            = ADC_RESOLUTION_12B;
    hadc1.Init.ScanConvMode          = DISABLE;
    hadc1.Init.ContinuousConvMode    = DISABLE;
    hadc1.Init.DiscontinuousConvMode = DISABLE;
    hadc1.Init.ExternalTrigConvEdge  = ADC_EXTERNALTRIGCONVEDGE_NONE;
    hadc1.Init.ExternalTrigConv      = ADC_SOFTWARE_START;
    hadc1.Init.DataAlign             = ADC_DATAALIGN_RIGHT;
    hadc1.Init.NbrOfConversion       = 1U;
    hadc1.Init.DMAContinuousRequests = DISABLE;
    hadc1.Init.EOCSelection          = ADC_EOC_SINGLE_CONV;
    HAL_ADC_Init(&hadc1);

    ch.Channel      = ADC_CHANNEL_1;
    ch.Rank         = 1U;
    ch.SamplingTime = ADC_SAMPLETIME_144CYCLES;
    HAL_ADC_ConfigChannel(&hadc1, &ch);
}

static uint32_t read_light(void)
{
    uint32_t value = 0U;

    HAL_ADC_Start(&hadc1);
    if (HAL_ADC_PollForConversion(&hadc1, 10U) == HAL_OK) {
        value = HAL_ADC_GetValue(&hadc1);
    }
    HAL_ADC_Stop(&hadc1);

    return value;
}

int main(void)
{
    HAL_Init();
    gpio_init();
    adc1_init();

    for (;;) {
        uint32_t light = read_light();

        HAL_GPIO_WritePin(BACKLIGHT_PORT, BACKLIGHT_PIN,
                          (light < DARK_LEVEL) ? GPIO_PIN_SET : GPIO_PIN_RESET);
        HAL_Delay(100U);
    }
}
