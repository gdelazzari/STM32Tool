STM32Tool
---------

Quick and dirty tool to create and manage STM32 projects

__NOTE:__ Linux only *(for now)*

### What's this?
This is a CLI *(Command Line Interface)* tool that helps during the development process of STM32 firmware projects. It reduces the hassle of configuring a new project, installing CMSIS and the new ST HAL libraries as well as configuring the linker script, startup files, etc...

> STM32CubeMX HAL libraries? Really?

Yes, I know there's a good amount of people that, in fact, *hates* the new ST HAL libraries, and I perfectly understand them (it's just insane to have that amount of code in an MCU, expecially in interrupt handling routines). But this tool isn't meant to be used by professionals, at least __not for now__. Check the *What will come next?* section at the end for more details.

### Who's this tool intended for
As I said this tool wasn't born to be used by STM32 gurus or people that works on them as their job.

Its intent is to make it easier for hobbists, makers, students, etc... to move from other, simpler, platforms (*AVR*, *PIC*, maybe *Arduino*?) to STM32 microcontrollers which, let's say, at a first glance are probably very confusing (as any other ARM microcontroller of any IC vendor). The new ST HAL libraries are, in my opinion, the best way to learn how the peripherals of the STM32 MCUs work and how you should use them. I think that the *"programming style"* of an ARM MCU is __really__ different from the way you program a PIC or an AVR: with ARM Cortex micrcontrollers you should use interrupts a lot more, and you also have DMA. It's a brand new world, and only an easy to use library will let you make the first steps.

Besided the choice of using the new libraries, the tool itself makes it really simple to start a new project (without worring, at the beginning, about CMSIS, linker scripts, startup files, etc...) by requiring the user to type just one command on the terminal. Just keep reading to better understand its capabilities.

It's also an attempt to get rid of all the Eclipse-based IDEs we have all around. I don't like them, they're just too heavy and sometimes confusing, besides also having a lot of features not required for someone that is just starting to develop for STM32.

### What can it do

This is what you can do with the tool (each thing you can do often translates to a command for the tool).

+ __Create new STM32 projects__ which will be already structured, with the latest ST HAL libraries loaded, a basic linker script and with CMSIS as well as the required device header file and startup file. The project will also include a ready-to-run Makefile.
+ __Compile your projects__ which, actually, calls `make` inside the project. But the tool also parses the output of `arm-none-eabi-size` and tells you in a more immediate way how much memory (Flash and RAM) you are using.
+ __Flash your projects__ on a physical board, using @texane's `stlink` tool
+ __Download ST HAL libraries__ automatically. The tool downloads the required library package when needed and, after extracting just the useful things, saves the new template package locally (from a 100+ MB .zip archive, just a ~3 MB one is saved locally)

### Ok then, how do I get started?

First off, you'll need:
+ A computer
+ With Linux (yes, I know. Check out *What will come next?* at the end)
+ Python 2.x (Python 3 isn't supported but it's coming very soon in the next commits)
+ The GCC compiler for ARM. On Ubuntu/Debian that should be as easy as `sudo apt-get install gcc-arm-none-eabi`. On Arch Linux there's a `arm-none-eabi-gcc` package available in the AUR.
+ @texane 's `stlink` tool, used to flash STM32 chips through an STLink programmer. Go to the repository and follow the instructions https://github.com/texane/stlink.
+ The `stm32flash` utility from @tormod on SourceForge, used to flash STM32 chips through the included bootloader. Go to the link, download and follow the instructions to compile and install https://sourceforge.net/projects/stm32flash/

> You'll probably require just one of the last two tools listed above, depending on your board. You can obviously have both installed if you want or if you need them. For the "tutorial" below we'll use a ST Nucleo board with the built-in STLink programmer, so the `stlink` utility is needed

Assuming you have all the required dependencies, let's install the tool. Just clone the repository and run `install.sh`

```
$ git clone https://github.com/gdelazzari/STM32Tool.git
$ cd STM32Tool
$ ./install.sh
```

Done. Now, let's see how you can create a new project to flash on your favourite board. Let's assume you have a NUCLEO-F072RB, which uses the [STM32F072RB](http://www.st.com/content/st_com/en/products/microcontrollers/stm32-32-bit-arm-cortex-mcus/stm32f0-series/stm32f0x2/stm32f072rb.html) MCU.

Fire up a terminal, change to your projects directory, and type

```
$ stm32tool new myProject -m STM32F072RB
```

Yes, that's all. The tool automatically downloads all the required things (if they cannot be found locally) and gets your brand new project up and running, with CMSIS configured as well as the ST HAL libraries. You can `cd` into it and run make, or you can preferably use

```
$ stm32tool build myProject
[INFO] Building project

Compilation successful, memory usage:
[FLASH]    0.6/128 kB	(0.4%)
[RAM]      1.5/16 kB	(9.6%)
```

Which, as you can see, gives you some information about the memory used by the code.

If you take a look at the new project structure, you'll see various files and directories

+ __src__ *directory*: guess what? Here you put your C and H files
+ __libs__ *directory*: this directory is intended for you to put in (possibly in subdirectories) the libraries you code depends on. If you download or write a library (made of C and H files), you should create a subdirectory for it and put all the files there.
+ __ldscripts__ *directory*: here are all the linker scripts for your MCU
+ __system__ *directory*: this contains CMSIS and the ST HAL libraries, as well as a couple of other files required by the MCU. You shouldn't change anything here.
+ __build__ *directory*: this will be filled up with object files but will also contain the ELF, HEX and BIN output files from the compilation and linking.
+ __Makefile__ (along with __dirs.mk__ and __config.mk__): this is your main Makefile, and you shouldn't change it. However you should take a look at __config.mk__ to see the configuration options available to you. The __dirs.mk__ contains the list of directories where C and H files are being searched. If you add a new directory under __src/__ or __libs/__, you must add an entry here.

Let's write some code to blink the LED on the Nucleo board. Open your `main.c` file under the __src__ directory and replace the content with:

```c
#include <stm32f0xx.h>

#include <stm32f0xx_hal.h>
#include <stm32f0xx_hal_rcc.h>
#include <stm32f0xx_hal_gpio.h>

int main(void)
{
  HAL_Init();

  __GPIOA_CLK_ENABLE();

  GPIO_InitTypeDef GPIO_Init;
  GPIO_Init.Pin = GPIO_PIN_5;
  GPIO_Init.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_Init.Speed = GPIO_SPEED_HIGH;
  HAL_GPIO_Init(GPIOA, &GPIO_Init);

  while (1) {
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_SET);
    HAL_Delay(250);
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_RESET);
    HAL_Delay(500);
  }

  return 0;
}

void SysTick_Handler(void) {
  HAL_IncTick();
}
```

> If you have a different board be sure to adapt the code to it. By the way this isn't a tutorial on how to program STM32 devices, it's just to show how to use this tool

Let's flash our project on our connected board:

```
$ stm32tool flash myProject
```

You'll see that the project gets compiled again (just the files changed are recompiled - it's always `make` in the background) and then flashed on you board using @texane's `stlink` utility.

> If you don't have the udev rules configured correctly and you can't program your device, try running the last command with `sudo`

> If you have a board without the STLink programmer built-in and you want to use the included bootloader, you can flash your project using `stm32tool flash-btl myProject`. Ensure that the correct serial port is set in `config.mk` inside the project directory. Remember to set the BOOT pins correctly and reset your device to make it start into bootloader mode before running the command

You should get your LED blinking.
I think this is more than enough to show you the workflow of this tool.

### Cool, what will come next?

A lot of questions will probably arise. First off, I want to say that this project (this little CLI tool), is just the beginning of a dream. I'm planning to build a new STM32 IDE based on [Atom](https://atom.io/), and this tool will be the the first step for managing projects on that future IDE.

I also wanted to say that getting it to run under Windows (and eventually Mac OS) is definitely on the roadmap (it probably works in the current state it is, but I haven't tested it and I don't really see the point right now: the workflow with this tool on Windows will probably be awful, I think I'll wait until I have a basic IDE up and running).

Regarding the HAL libraries thing, I'm planning to let the user choose (during project creation) from a set of different templates. They'll be, for sure, __barebone__, __Standard Peripheral Library__ and __CubeMX HAL libraries__. Eventually, it would be nice to have some RTOS's templates available. It would be even nicer to set up a *"repository"* of community-made template packages, but that's not an immediate thing.

And, in case you are wondering, debugging isn't supported for now (well, you can fire up the `st-util` server and then `gdb` manually, but it's not really funny), but on a future IDE getting debug integrated will be absolutely high on the list.

By the way, thank you for checking out this. I hope I have somehow caught your interest. Please give feedback if you find all of this useful, that will be really appreciated!
