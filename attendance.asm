.data
arr: .word 101, 102, 105, 110
n:   .word 4

sum_msg: .asciiz "\nSum: "
avg_msg: .asciiz "\nAverage: "
max_msg: .asciiz "\nMax Roll No: "
count_msg: .asciiz "\nTotal Students: "

.text
.globl main

main:
    la t0, arr
    lw t1, n

    li t2, 0
    li t3, 0
    li t4, 0

loop:
    beq t4, t1, done

    lw t5, 0(t0)
    add t2, t2, t5

    bge t5, t3, update
    j skip

update:
    mv t3, t5

skip:
    addi t0, t0, 4
    addi t4, t4, 1
    j loop

done:
    div t6, t2, t1

    li a7, 4
    la a0, count_msg
    ecall
    li a7, 1
    mv a0, t1
    ecall

    li a7, 4
    la a0, sum_msg
    ecall
    li a7, 1
    mv a0, t2
    ecall

    li a7, 4
    la a0, avg_msg
    ecall
    li a7, 1
    mv a0, t6
    ecall

    li a7, 4
    la a0, max_msg
    ecall
    li a7, 1
    mv a0, t3
    ecall

    li a7, 10
    ecall