#include "stm32f4xx_hal.h"

#define CS_PORT         GPIOA
#define CS_PIN          GPIO_PIN_4
#define FRAME_LEN       4U

SPI_HandleTypeDef hspi1;

static uint8_t spi_done;
static uint8_t tx_frame[FRAME_LEN];

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
    gpio.Speed     = GPIO_SPEED_FREQ_LOW;
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
    hspi1.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_16;
    hspi1.Init.FirstBit          = SPI_FIRSTBIT_MSB;
    hspi1.Init.TIMode            = SPI_TIMODE_DISABLE;
    hspi1.Init.CRCCalculation    = SPI_CRCCALCULATION_DISABLE;
    hspi1.Init.CRCPolynomial     = 10U;
    HAL_SPI_Init(&hspi1);

    HAL_NVIC_SetPriority(SPI1_IRQn, 7, 0);
    HAL_NVIC_EnableIRQ(SPI1_IRQn);
}

void SPI1_IRQHandler(void)
{
    HAL_SPI_IRQHandler(&hspi1);
}

void HAL_SPI_TxCpltCallback(SPI_HandleTypeDef *hspi)
{
    if (hspi->Instance == SPI1) {
        spi_done = 1U;
    }
}

static void write_register(uint8_t reg, uint16_t value)
{
    tx_frame[0] = 0x80U | reg;
    tx_frame[1] = (uint8_t)(value >> 8);
    tx_frame[2] = (uint8_t)(value & 0xFFU);
    tx_frame[3] = 0U;

    spi_done = 0U;
    HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_RESET);
    HAL_SPI_Transmit_IT(&hspi1, tx_frame, FRAME_LEN);

    while (spi_done == 0U) {
    }

    HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_SET);
}

int main(void)
{
    uint16_t level = 0U;

    HAL_Init();
    spi1_init();

    for (;;) {
        write_register(0x12U, level);
        level = (uint16_t)((level + 64U) & 0x0FFFU);
        HAL_Delay(10U);
    }
}
