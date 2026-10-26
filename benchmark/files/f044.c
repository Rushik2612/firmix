#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"

#define LED_PORT        GPIOB
#define LED_PIN         GPIO_PIN_0
#define SAMPLE_QUEUE_LEN 16U
#define LIMIT           3200U

ADC_HandleTypeDef hadc1;

static QueueHandle_t sample_queue;

static void gpio_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    gpio.Pin  = GPIO_PIN_1;
    gpio.Mode = GPIO_MODE_ANALOG;
    gpio.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin   = LED_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &gpio);
}

static void adc1_init(void)
{
    ADC_ChannelConfTypeDef ch = {0};

    __HAL_RCC_ADC1_CLK_ENABLE();

    hadc1.Instance                   = ADC1;
    hadc1.Init.ClockPrescaler        = ADC_CLOCK_SYNC_PCLK_DIV8;
    hadc1.Init.Resolution            = ADC_RESOLUTION_12B;
    hadc1.Init.ScanConvMode          = DISABLE;
    hadc1.Init.ContinuousConvMode    = ENABLE;
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
    ch.SamplingTime = ADC_SAMPLETIME_480CYCLES;
    HAL_ADC_ConfigChannel(&hadc1, &ch);

    HAL_NVIC_SetPriority(ADC_IRQn, 7, 0);
    HAL_NVIC_EnableIRQ(ADC_IRQn);
}

void ADC_IRQHandler(void)
{
    HAL_ADC_IRQHandler(&hadc1);
}

static void post_sample(uint16_t value)
{
    xQueueSendToBack(sample_queue, &value, 0);
}

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
    if (hadc->Instance == ADC1) {
        post_sample((uint16_t)HAL_ADC_GetValue(hadc));
    }
}

static void monitor_task(void *arg)
{
    uint16_t value;

    (void)arg;

    for (;;) {
        if (xQueueReceive(sample_queue, &value, portMAX_DELAY) == pdTRUE) {
            HAL_GPIO_WritePin(LED_PORT, LED_PIN,
                              (value > LIMIT) ? GPIO_PIN_SET : GPIO_PIN_RESET);
        }
    }
}

int main(void)
{
    HAL_Init();
    gpio_init();

    sample_queue = xQueueCreate(SAMPLE_QUEUE_LEN, sizeof(uint16_t));
    adc1_init();

    xTaskCreate(monitor_task, "monitor", 128, NULL, 2, NULL);
    HAL_ADC_Start_IT(&hadc1);
    vTaskStartScheduler();

    for (;;) {
    }
}
