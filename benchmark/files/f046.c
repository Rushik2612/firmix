#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define THRESHOLD       1800U

ADC_HandleTypeDef hadc1;

static SemaphoreHandle_t adc_mutex;
static SemaphoreHandle_t wake_sem;

static void hw_init(void)
{
    GPIO_InitTypeDef gpio = {0};
    ADC_ChannelConfTypeDef ch = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_ADC1_CLK_ENABLE();

    gpio.Pin  = GPIO_PIN_4;
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

    ch.Channel      = ADC_CHANNEL_4;
    ch.Rank         = 1U;
    ch.SamplingTime = ADC_SAMPLETIME_56CYCLES;
    HAL_ADC_ConfigChannel(&hadc1, &ch);
}

static int adc_read_locked(uint16_t *out)
{
    int status = -2;

    if (xSemaphoreTake(adc_mutex, pdMS_TO_TICKS(50)) != pdTRUE) {
        return -1;
    }

    HAL_ADC_Start(&hadc1);
    if (HAL_ADC_PollForConversion(&hadc1, 10U) != HAL_OK) {
        goto out;
    }

    *out = (uint16_t)HAL_ADC_GetValue(&hadc1);
    status = 0;

out:
    HAL_ADC_Stop(&hadc1);
    xSemaphoreGive(adc_mutex);
    return status;
}

static void pacer_task(void *arg)
{
    (void)arg;

    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(100));
        xSemaphoreGive(wake_sem);
    }
}

static void level_task(void *arg)
{
    uint16_t level;

    (void)arg;

    for (;;) {
        if (xSemaphoreTake(wake_sem, portMAX_DELAY) == pdTRUE) {
            if (adc_read_locked(&level) == 0) {
                HAL_GPIO_WritePin(LED_PORT, LED_PIN,
                                  (level > THRESHOLD) ? GPIO_PIN_SET : GPIO_PIN_RESET);
            }
        }
    }
}

int main(void)
{
    HAL_Init();
    hw_init();

    adc_mutex = xSemaphoreCreateMutex();
    wake_sem = xSemaphoreCreateBinary();

    xTaskCreate(pacer_task, "pacer", 128, NULL, 1, NULL);
    xTaskCreate(level_task, "level", 128, NULL, 2, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
