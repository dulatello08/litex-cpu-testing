BUILD_DIR=../build/soc

include $(BUILD_DIR)/software/include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

OBJECTS = crt0.o main.o

all: firmware.bin

%.o: %.c
	$(compile)

crt0.o: $(CPU_DIRECTORY)/crt0.S
	$(assemble)

firmware.elf: $(OBJECTS)
	$(CC) $(LDFLAGS) -T linker.ld -N -o $@ \
		$(OBJECTS) \
		$(PACKAGES:%=-L$(BUILD_DIR)/software/%) \
		-L$(BUILD_DIR)/software/libbase \
		-L$(BUILD_DIR)/software/libc \
		-L$(BUILD_DIR)/software/libcompiler_rt \
		-lc -lbase -lcompiler_rt

firmware.bin: firmware.elf
	$(OBJCOPY) -O binary $< $@

clean:
	rm -f $(OBJECTS) firmware.elf firmware.bin

.PHONY: all clean
