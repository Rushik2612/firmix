#include "stm32f4xx_hal.h"

#define CS_PORT         GPIOA
#define CS_PIN          GPIO_PIN_4
#define FRAME_BYTES     4U

SPI_HandleTypeDef hspi1;

static uint8_t frame[FRAME_BYTES] = { 0xA5U, 0x00U, 0x00U, 0x5AU };

void HAL_SPI_MspInit(SPI_HandleTypeDef *hspi)
{
    GPIO_InitTypeDef gpio = {0};

    if (hspi->Instance == SPI1) {
        __HAL_RCC_SPI1_CLK_ENABLE();
        __HAL_RCC_GPIOA_CLK_ENABLE();

        gpio.Pin       = GPIO_PIN_5 | GPIO_PIN_6 | GPIO_PIN_7;
        gpio.Mode      = GPIO_MODE_AF_PP;
        gpio.Pull      = GPIO_NOPULL;
        gpio.Speed     = GPIO_SPEED_FREQ_VERY_HIGH;
        gpio.Alternate = GPIO_AF5_SPI1;
        HAL_GPIO_Init(GPIOA, &gpio);
    }
}

static void cs_init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();

    gpio.Pin   = CS_PIN;
    gpio.Mode  = GPIO_MODE_OUTPUT_PP;
    gpio.Pull  = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(CS_PORT, &gpio);
    HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_SET);
}

static void spi1_init(void)
{
    hspi1.Instance               = SPI1;
    hspi1.Init.Mode              = SPI_MODE_MASTER;
    hspi1.Init.Direction         = SPI_DIRECTION_2LINES;
    hspi1.Init.DataSize          = SPI_DATASIZE_8BIT;
    hspi1.Init.CLKPolarity       = SPI_POLARITY_HIGH;
    hspi1.Init.CLKPhase          = SPI_PHASE_2EDGE;
    hspi1.Init.NSS               = SPI_NSS_SOFT;
    hspi1.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_32;
    hspi1.Init.FirstBit          = SPI_FIRSTBIT_MSB;
    HAL_SPI_Init(&hspi1);
}

int main(void)
{
    HAL_Init();
    cs_init();
    spi1_init();

    for (;;) {
        HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_RESET);
        HAL_SPI_Transmit(&hspi1, frame, FRAME_BYTES, 20U);
        HAL_GPIO_WritePin(CS_PORT, CS_PIN, GPIO_PIN_SET);
        frame[1]++;
        HAL_Delay(100U);
    }
}
