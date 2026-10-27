#include "stm32f4xx_hal.h"

#define RING_LEN        32U
#define WINDOW          8U
#define LED_PORT        GPIOB
#define LED_PIN         GPIO_PIN_7
#define LIMIT           3000U

ADC_HandleTypeDef hadc1;

static uint16_t ring[RING_LEN];
static uint32_t head;
static uint32_t filled;

static void adc_init(void)
{
    GPIO_InitTypeDef gpio = {0};
    ADC_ChannelConfTypeDef ch = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_ADC1_CLK_ENABLE();

    gpio.Pin  = GPIO_PIN_1;
    gpio.Mode = GPIO_MODE_ANALOG;
    gpio.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin   = LED_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &gpio);

    hadc1.Instance                = ADC1;
    hadc1.Init.ClockPrescaler     = ADC_CLOCK_SYNC_PCLK_DIV4;
    hadc1.Init.Resolution         = ADC_RESOLUTION_12B;
    hadc1.Init.ScanConvMode       = DISABLE;
    hadc1.Init.ContinuousConvMode = DISABLE;
    hadc1.Init.ExternalTrigConv   = ADC_SOFTWARE_START;
    hadc1.Init.DataAlign          = ADC_DATAALIGN_RIGHT;
    hadc1.Init.NbrOfConversion    = 1U;
    HAL_ADC_Init(&hadc1);

    ch.Channel      = ADC_CHANNEL_1;
    ch.Rank         = 1U;
    ch.SamplingTime = ADC_SAMPLETIME_56CYCLES;
    HAL_ADC_ConfigChannel(&hadc1, &ch);
}

static void ring_push(uint16_t v)
{
    ring[head] = v;
    head = (head + 1U) % RING_LEN;
    if (filled < RING_LEN) {
        filled++;
    }
}

static uint32_t window_average(void)
{
    uint32_t n = (filled < WINDOW) ? filled : WINDOW;
    uint32_t sum = 0U;
    uint32_t i;

    if (n == 0U) {
        return 0U;
    }
    for (i = 0U; i < n; i++) {
        uint32_t idx = (head + RING_LEN - 1U - i) % RING_LEN;
        sum += ring[idx];
    }
    return sum / n;
}

int main(void)
{
    HAL_Init();
    adc_init();

    for (;;) {
        HAL_ADC_Start(&hadc1);
        if (HAL_ADC_PollForConversion(&hadc1, 10U) == HAL_OK) {
            ring_push((uint16_t)HAL_ADC_GetValue(&hadc1));
        }
        HAL_ADC_Stop(&hadc1);

        if (window_average() > LIMIT) {
            HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);
        } else {
            HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_RESET);
        }
        HAL_Delay(20U);
    }
}
