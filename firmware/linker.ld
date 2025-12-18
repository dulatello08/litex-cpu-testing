INCLUDE generated/output_format.ld
ENTRY(_start)

__DYNAMIC = 0;

INCLUDE generated/regions.ld

SECTIONS
{
	.text :
	{
		_ftext = .;
		/* Make sure crt0 files come first, and they, and the isr */
		/* don't get disposed of by greedy optimization */
		*crt0*(.text)
		KEEP(*crt0*(.text))
		KEEP(*(.text.isr))

		*(.text .stub .text.* .gnu.linkonce.t.*)
		_etext = .;
	} > main_ram

	.rodata :
	{
		. = ALIGN(4);
		_frodata = .;
		*(.rodata .rodata.* .gnu.linkonce.r.*)
		*(.rodata1)
		_erodata = .;
	} > main_ram

	.data :
	{
		. = ALIGN(4);
		_fdata = .;
		*(.data .data.* .gnu.linkonce.d.*)
		*(.data1)
		_gp = ALIGN(16);
		*(.sdata .sdata.* .gnu.linkonce.s.*)
		_edata = .;
	} > main_ram

	_fdata_rom = LOADADDR(.data);

	.bss :
	{
		. = ALIGN(4);
		_fbss = .;
		*(.dynsbss)
		*(.sbss .sbss.* .gnu.linkonce.sb.*)
		*(.scommon)
		*(.dynbss)
		*(.bss .bss.* .gnu.linkonce.b.*)
		*(COMMON)
		. = ALIGN(4);
		_ebss = .;
		_end = .;
	} > main_ram
}

PROVIDE(_fstack = ORIGIN(main_ram) + LENGTH(main_ram) - 4);
