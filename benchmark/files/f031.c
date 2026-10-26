#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

#define SENSOR_ADDR     (0x48U << 1)
#define REG_TEMP        0x00U
#define LED_PORT        GPIOA
#define LED_PIN         GPIO_PIN_5
#define TEMP_LIMIT      60U

I2C_HandleTypeDef hi2c1;

static SemaphoreHandle_t bus_mutex;

static void i2c1_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
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
    gpio.Alternate = 0U;
    HAL_GPIO_Init(LED_PORT, &gpio);

    hi2c1.Instance             = I2C1;
    hi2c1.Init.ClockSpeed      = 400000U;
    hi2c1.Init.DutyCycle       = I2C_DUTYCYCLE_2;
    hi2c1.Init.OwnAddress1     = 0U;
    hi2c1.Init.AddressingMode  = I2C_ADDRESSINGMODE_7BIT;
    hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
    hi2c1.Init.OwnAddress2     = 0U;
    hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
    hi2c1.Init.NoStretchMode   = I2C_NOSTRETCH_DISABLE;
    HAL_I2C_Init(&hi2c1);
}

static int sensor_read(uint8_t reg, uint8_t *out)
{
    if (xSemaphoreTake(bus_mutex, pdMS_TO_TICKS(20)) != pdTRUE) {
        return -1;
    }

    if (HAL_I2C_Master_Transmit(&hi2c1, SENSOR_ADDR, &reg, 1U, 20U) != HAL_OK) {
        return -2;
    }

    if (HAL_I2C_Master_Receive(&hi2c1, SENSOR_ADDR, out, 1U, 20U) != HAL_OK) {
        xSemaphoreGive(bus_mutex);
        return -3;
    }

    xSemaphoreGive(bus_mutex);
    return 0;
}

static void temp_task(void *arg)
{
    uint8_t temp;

    (void)arg;

    for (;;) {
        if (sensor_read(REG_TEMP, &temp) == 0) {
            HAL_GPIO_WritePin(LED_PORT, LED_PIN,
                              (temp > TEMP_LIMIT) ? GPIO_PIN_SET : GPIO_PIN_RESET);
        }
        vTaskDelay(pdMS_TO_TICKS(250));
    }
}

static void probe_task(void *arg)
{
    uint8_t dummy;

    (void)arg;

    for (;;) {
        (void)sensor_read(0x07U, &dummy);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

int main(void)
{
    HAL_Init();
    i2c1_init();

    bus_mutex = xSemaphoreCreateMutex();

    xTaskCreate(temp_task, "temp", 128, NULL, 2, NULL);
    xTaskCreate(probe_task, "probe", 128, NULL, 1, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
