#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

#define SENSOR_ADDR     (0x48U << 1)
#define REG_TEMP        0x00U
#define ALARM_LIMIT     600
#define LED_PORT        GPIOC
#define LED_PIN         GPIO_PIN_13

I2C_HandleTypeDef hi2c1;

static SemaphoreHandle_t i2c_mutex;
static int16_t last_temp;

static void board_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();
    __HAL_RCC_I2C1_CLK_ENABLE();

    gpio.Pin       = GPIO_PIN_8 | GPIO_PIN_9;
    gpio.Mode      = GPIO_MODE_AF_OD;
    gpio.Pull      = GPIO_PULLUP;
    gpio.Speed     = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF4_I2C1;
    HAL_GPIO_Init(GPIOB, &gpio);

    gpio.Pin       = LED_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(LED_PORT, &gpio);

    hi2c1.Instance             = I2C1;
    hi2c1.Init.ClockSpeed      = 100000U;
    hi2c1.Init.DutyCycle       = I2C_DUTYCYCLE_2;
    hi2c1.Init.AddressingMode  = I2C_ADDRESSINGMODE_7BIT;
    hi2c1.Init.NoStretchMode   = I2C_NOSTRETCH_DISABLE;
    HAL_I2C_Init(&hi2c1);
}

static int32_t sensor_read_temp(int16_t *out)
{
    uint8_t raw[2];

    if (xSemaphoreTake(i2c_mutex, pdMS_TO_TICKS(50)) != pdTRUE) {
        return -1;
    }
    if (HAL_I2C_Mem_Read(&hi2c1, SENSOR_ADDR, REG_TEMP, I2C_MEMADD_SIZE_8BIT, raw, 2U, 20U) != HAL_OK) {
    xSemaphoreGive(i2c_mutex);
    return -2;
    }
    *out = (int16_t)(((uint16_t)raw[0] << 8) | raw[1]);
    xSemaphoreGive(i2c_mutex);
    return 0;
}

static void temp_task(void *arg)
{
    int16_t t;
    (void)arg;

    for (;;) {
        if (sensor_read_temp(&t) == 0) {
            last_temp = t;
            if (t > ALARM_LIMIT) {
                HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_SET);
            } else {
                HAL_GPIO_WritePin(LED_PORT, LED_PIN, GPIO_PIN_RESET);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(250));
    }
}

int main(void)
{
    HAL_Init();
    board_init();

    i2c_mutex = xSemaphoreCreateMutex();
    xTaskCreate(temp_task, "temp", 256, NULL, 2, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
