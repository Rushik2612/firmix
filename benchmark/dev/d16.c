#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

#define CS_PORT         GPIOA
#define CS_PIN          GPIO_PIN_4
#define CMD_READ_ID     0x9FU

SPI_HandleTypeDef hspi1;

static SemaphoreHandle_t spi_mutex;
static uint32_t flash_id;

static void spi1_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_SPI1_CLK_ENABLE();

    gpio.Pin       = GPIO_PIN_5 | GPIO_PIN_6 | GPIO_PIN_7;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF5_SPI1;
    HAL_GPIO_Init(GPIOA, &gpio);

    gpio.Pin       = CS_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Alternate = 0U;
    HAL_GPIO_Init(CS_PORT, &gpio);
    HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_SET);

    hspi1.Instance               = SPI1;
    hspi1.Init.Mode              = SPI_MODE_MASTER;
    hspi1.Init.Direction         = SPI_DIRECTION_2LINES;
    hspi1.Init.DataSize          = SPI_DATASIZE_8BIT;
    hspi1.Init.CLKPolarity       = SPI_POLARITY_LOW;
    hspi1.Init.CLKPhase          = SPI_PHASE_1EDGE;
    hspi1.Init.NSS               = SPI_NSS_SOFT;
    hspi1.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_8;
    hspi1.Init.FirstBit          = SPI_FIRSTBIT_MSB;
    HAL_SPI_Init(&hspi1);
}

static int flash_read_id(uint32_t *id)
{
    int rc = -1;
    uint8_t cmd = CMD_READ_ID;
    uint8_t buf[3];

    if (xSemaphoreTake(spi_mutex, pdMS_TO_TICKS(50)) != pdTRUE) {
        return -1;
    }
    HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_RESET);
    if (HAL_SPI_Transmit(&hspi1, &cmd, 1U, 20U) != HAL_OK) {
        goto out;
    }
    if (HAL_SPI_Receive(&hspi1, buf, 3U, 20U) != HAL_OK) {
        goto out;
    }
    *id = ((uint32_t)buf[0] << 16) | ((uint32_t)buf[1] << 8) | buf[2];
    rc = 0;
out:
    HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_SET);
    xSemaphoreGive(spi_mutex);
    return rc;
}

static void flash_task(void *arg)
{
    uint32_t id;
    (void)arg;

    for (;;) {
        if (flash_read_id(&id) == 0) {
            flash_id = id;
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

int main(void)
{
    HAL_Init();
    spi1_init();

    spi_mutex = xSemaphoreCreateMutex();
    xTaskCreate(flash_task, "flash", 256, NULL, 2, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
