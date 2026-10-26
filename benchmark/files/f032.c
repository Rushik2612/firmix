#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

#define CS_PORT         GPIOB
#define CS_PIN          GPIO_PIN_12
#define STORE_SIZE      0x10000UL
#define ERR_BUSY        (-1)
#define ERR_RANGE       (-2)
#define ERR_CMD         (-3)

typedef enum {
    STORE_READ,
    STORE_ERASE,
    STORE_PROBE
} store_cmd_t;

SPI_HandleTypeDef hspi2;

static SemaphoreHandle_t store_mutex;

static void spi2_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_SPI2_CLK_ENABLE();

    gpio.Pin       = GPIO_PIN_13 | GPIO_PIN_14 | GPIO_PIN_15;
    gpio.Mode      = GPIO_MODE_AF_PP;
    gpio.Pull      = GPIO_NOPULL;
    gpio.Speed     = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF5_SPI2;
    HAL_GPIO_Init(GPIOB, &gpio);

    gpio.Pin       = CS_PIN;
    gpio.Mode      = GPIO_MODE_OUTPUT_PP;
    gpio.Speed     = GPIO_SPEED_FREQ_LOW;
    gpio.Alternate = 0U;
    HAL_GPIO_Init(CS_PORT, &gpio);
    HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_SET);

    hspi2.Instance               = SPI2;
    hspi2.Init.Mode              = SPI_MODE_MASTER;
    hspi2.Init.Direction         = SPI_DIRECTION_2LINES;
    hspi2.Init.DataSize          = SPI_DATASIZE_8BIT;
    hspi2.Init.CLKPolarity       = SPI_POLARITY_LOW;
    hspi2.Init.CLKPhase          = SPI_PHASE_1EDGE;
    hspi2.Init.NSS               = SPI_NSS_SOFT;
    hspi2.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_8;
    hspi2.Init.FirstBit          = SPI_FIRSTBIT_MSB;
    hspi2.Init.TIMode            = SPI_TIMODE_DISABLE;
    hspi2.Init.CRCCalculation    = SPI_CRCCALCULATION_DISABLE;
    hspi2.Init.CRCPolynomial     = 10U;
    HAL_SPI_Init(&hspi2);
}

static int spi_op(uint8_t opcode, uint32_t addr)
{
    uint8_t frame[4];

    frame[0] = opcode;
    frame[1] = (uint8_t)(addr >> 16);
    frame[2] = (uint8_t)(addr >> 8);
    frame[3] = (uint8_t)addr;

    HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_RESET);
    HAL_StatusTypeDef st = HAL_SPI_Transmit(&hspi2, frame, 4U, 20U);
    HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_SET);

    return (st == HAL_OK) ? 0 : ERR_BUSY;
}

static int store_command(store_cmd_t cmd, uint32_t addr)
{
    int status;

    if (xSemaphoreTake(store_mutex, pdMS_TO_TICKS(100)) != pdTRUE) {
        return ERR_BUSY;
    }

    switch (cmd) {
    case STORE_READ:
        status = spi_op(0x03U, addr);
        break;
    case STORE_ERASE:
        if (addr >= STORE_SIZE) {
            return ERR_RANGE;
        }
        status = spi_op(0x20U, addr);
        break;
    case STORE_PROBE:
        status = spi_op(0x9FU, 0U);
        break;
    default:
        status = ERR_CMD;
        break;
    }

    xSemaphoreGive(store_mutex);
    return status;
}

static void maintenance_task(void *arg)
{
    uint32_t sector = 0U;

    (void)arg;

    for (;;) {
        (void)store_command(STORE_ERASE, sector);
        sector = (sector + 0x1000UL) % (STORE_SIZE + 0x1000UL);
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}

static void reader_task(void *arg)
{
    (void)arg;

    for (;;) {
        (void)store_command(STORE_READ, 0x100UL);
        vTaskDelay(pdMS_TO_TICKS(200));
    }
}

int main(void)
{
    HAL_Init();
    spi2_init();

    store_mutex = xSemaphoreCreateMutex();

    xTaskCreate(maintenance_task, "maint", 192, NULL, 1, NULL);
    xTaskCreate(reader_task, "reader", 192, NULL, 2, NULL);
    vTaskStartScheduler();

    for (;;) {
    }
}
