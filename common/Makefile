-include config.mk
-include dirs.mk

# Flags for compilation and linking
FLAGS := $(OPTIMIZE) $(CSTD) $(MCU) -ffunction-sections -fdata-sections -ffreestanding -flto -fno-move-loop-invariants -Wall -Wno-strict-aliasing

SOURCES_WD := $(foreach dir, $(DIRS), $(wildcard $(dir)/*.c))
INCLUDES := $(foreach dir, $(DIRS), -I"$(dir)")

LDSCRIPTS := $(wildcard ldscripts/*.ld)

LDFLAGS := -T"mem.ld" $(foreach script, $(filter-out mem.ld, $(notdir $(LDSCRIPTS))), -T"$(script)")

MKFILE_PATH := $(abspath $(lastword $(MAKEFILE_LIST)))
DIR_NAME := $(notdir $(patsubst %/,%,$(dir $(MKFILE_PATH))))

ELF := build/$(DIR_NAME).elf
HEX := build/$(DIR_NAME).hex
BIN := build/$(DIR_NAME).bin
MAP := build/$(DIR_NAME).map

vpath %.c $(DIRS)

SOURCES := $(notdir $(SOURCES_WD))
OBJECTS := $(patsubst %.c,build/obj/%.o,$(SOURCES))

all: $(ELF) $(HEX) size

build/obj/%.o : %.c | build_dirs
	@echo 'Compiling $<'
	@arm-none-eabi-gcc $(CPU) $(ISET) $(FLAGS) $(INCLUDES) -c -o "$@" "$<"

$(ELF) : $(OBJECTS)
	@echo 'Linking target $(ELF)'
	@arm-none-eabi-gcc $(CPU) $(ISET) $(FLAGS) $(LDFLAGS) -Xlinker --gc-sections -L"ldscripts" -Wl,-Map,"$(MAP)" --specs=nano.specs -o $(ELF) $(STARTUP) $(OBJECTS)

$(HEX) : $(ELF)
	@echo 'Building HEX file $(HEX)'
	@arm-none-eabi-objcopy -O ihex "$(ELF)" "$(HEX)"

$(BIN) : $(ELF)
	@echo 'Building binary output file $(BIN)'
	@arm-none-eabi-objcopy -O binary "$(ELF)" "$(BIN)"

program: $(BIN)
	@echo 'Programming device with $(BIN) (STlink)'
	@st-flash --reset write $(BIN) 0x8000000

program-btl: $(BIN)
	@echo 'Programming device with $(BIN) (bootloader)'
	@stm32flash $(BTLPORT) -b 115200 -w $(BIN) -g 0x0

build_dirs:
	@mkdir -p build
	@mkdir -p build/obj

size: $(ELF)
	@arm-none-eabi-size --format=berkeley $(ELF)

clean:
	rm -R -f build/*
