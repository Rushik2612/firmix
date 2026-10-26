#include "stm32f4xx_hal.h"

#define HIST_BINS       10U
#define BIN_WIDTH       400U
#define SAMPLES         64U
#define LED_PORT        GPIOB
#define LED_PIN         GPIO_PIN_1

ADC_HandleTypeDef hadc1;

static uint16_t histogram[HIST_BINS];

static void hw_init(void)
{
    GPIO_InitTypeDef gpio = {0};
    ADC_ChannelConfTypeDef ch = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_ADC1_CLK_ENABLE();

    gpio.Pin  = GPIO_PIN_6;
    gpio.Mode = GPIO_MODE_ANALOG;
    gpio.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin   = LED_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &gpio);

    hadc1.Instance                   = ADC1;
    hadc1.Init.ClockPrescaler        = ADC_CLOCK_SYNC_PCLK_DIV4;
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

    ch.Channel      = ADC_CHANNEL_6;
    ch.Rank         = 1U;
    ch.SamplingTime = ADC_SAMPLETIME_144CYCLES;
    HAL_ADC_ConfigChannel(&hadc1, &ch);
}

static void collect_histogram(void)
{
    uint32_t i;
    uint32_t value;

    for (i = 0U; i < HIST_BINS; i++) {
        histogram[i] = 0U;
    }

    for (i = 0U; i < SAMPLES; i++) {
        HAL_ADC_Start(&hadc1);
        if (HAL_ADC_PollForConversion(&hadc1, 10U) == HAL_OK) {
            value = HAL_ADC_GetValue(&hadc1);
            histogram[value / BIN_WIDTH]++;
        }
        HAL_ADC_Stop(&hadc1);
    }
}

static uint32_t busiest_bin(void)
{
    uint32_t best = 0U;
    uint32_t i;

    for (i = 1U; i < HIST_BINS; i++) {
        if (histogram[i] > histogram[best]) {
            best = i;
        }
    }
    return best;
}

int main(void)
{
    HAL_Init();
    hw_init();

    for (;;) {
        collect_histogram();
        HAL_GPIO_WritePin(LED_PORT, LED_PIN,
                          (busiest_bin() >= 5U) ? GPIO_PIN_SET : GPIO_PIN_RESET);
        HAL_Delay(500U);
    }
}
